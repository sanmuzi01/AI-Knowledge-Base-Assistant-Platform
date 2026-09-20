"""外部告警推送服务：管理用户的 Webhook 通道 + 往外发一条告警。

只做 Webhook（飞书/钉钉/企业微信自定义机器人、Slack Incoming Webhook、或用户自建接收端都是
一个接受 JSON POST 的 URL），不做邮件/短信——那些需要额外的发信基础设施，Webhook 零依赖
就能覆盖群机器人这个最高频场景。

出站 URL 完全由用户填写，复用 web_crawler_service.validate_crawl_url 做 SSRF 校验
（挡内网 / localhost / 云元数据地址），和 service/widgets/connectors/http_api.py 的做法一致。
"""

import asyncio
from typing import Any, Dict, List, Optional

from utils.logger_handler import get_logger
from utils.timeutil import utcnow

from models import notification_channel_async_dao as dao
from service.exceptions import InvalidInput, NotFound

logger = get_logger("notification_service")


def _channel_payload(channel) -> Dict[str, Any]:
    return {
        "id": channel.id,
        "name": channel.name,
        "kind": channel.kind,
        "webhook_url": channel.webhook_url,
        "is_enabled": bool(channel.is_enabled),
        "last_sent_at": channel.last_sent_at.strftime("%Y-%m-%d %H:%M:%S") if channel.last_sent_at else None,
        "last_error": channel.last_error,
    }


async def list_channels(db, user_id: int) -> List[Dict[str, Any]]:
    channels = await dao.list_channels_async(db, user_id)
    return [_channel_payload(c) for c in channels]


async def _validate_webhook_url(raw_url: str) -> str:
    from service.web_crawler_service import CrawlerError, validate_crawl_url

    try:
        return await asyncio.to_thread(validate_crawl_url, raw_url)
    except CrawlerError as exc:
        raise InvalidInput(f"这个 Webhook 地址不允许使用：{exc}") from exc


async def create_channel(db, user_id: int, name: str, webhook_url: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise InvalidInput("请填写通道名称")
    url = await _validate_webhook_url(webhook_url)
    channel = await dao.create_channel_async(db, user_id, name, url)
    return _channel_payload(channel)


async def update_channel(db, user_id: int, channel_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    channel = await dao.get_owned_channel_async(db, user_id, channel_id)
    if not channel:
        raise NotFound("通知通道不存在")
    fields: Dict[str, Any] = {}
    if "name" in patch and (patch["name"] or "").strip():
        fields["name"] = patch["name"].strip()
    if "webhook_url" in patch and patch["webhook_url"]:
        fields["webhook_url"] = await _validate_webhook_url(patch["webhook_url"])
    if "is_enabled" in patch and patch["is_enabled"] is not None:
        fields["is_enabled"] = 1 if patch["is_enabled"] else 0
    if not fields:
        raise InvalidInput("没有需要更新的内容")
    channel = await dao.update_channel_async(db, channel, fields)
    return _channel_payload(channel)


async def delete_channel(db, user_id: int, channel_id: int) -> Dict[str, Any]:
    channel = await dao.get_owned_channel_async(db, user_id, channel_id)
    if not channel:
        raise NotFound("通知通道不存在")
    await dao.delete_channel_async(db, channel)
    return {"message": "通道已删除", "id": channel_id}


def _build_webhook_body(title: str, message: str) -> Dict[str, Any]:
    """飞书/钉钉自定义机器人都认识 `{"msg_type":"text","content":{"text":...}}` 这个形状；

    不认识这个形状的接收端（Slack、用户自建服务）大多也能从里面找到 `text` 字段，
    额外把标题/正文原样铺开在顶层，方便自建端直接读字段而不用解析机器人专用格式。
    """
    text = f"{title}\n{message}"
    return {
        "msg_type": "text",
        "content": {"text": text},
        "text": text,
        "title": title,
        "message": message,
    }


async def _send_to_channel(channel, title: str, message: str) -> Optional[str]:
    """发一条到单个通道。成功返回 None，失败返回错误信息（调用方决定要不要落库）。"""
    from service.http_resilience import async_request_with_retry
    from service.web_crawler_service import CrawlerError, validate_crawl_url

    try:
        url = await asyncio.to_thread(validate_crawl_url, channel.webhook_url)
    except CrawlerError as exc:
        return f"URL 校验失败：{exc}"

    body = _build_webhook_body(title, message)
    host = url.split("//", 1)[-1].split("/", 1)[0]
    try:
        response = await async_request_with_retry(
            service_name=f"notification_webhook:{host}",
            sender=lambda client: client.post(url, json=body),
            timeout_env="NOTIFICATION_WEBHOOK_TIMEOUT_SECONDS",
            default_timeout=8.0,
            retry_env="NOTIFICATION_WEBHOOK_MAX_RETRIES",
            default_retries=1,
        )
        response.raise_for_status()
        return None
    except Exception as exc:  # noqa: BLE001 - 推送失败只记录，不能影响组件运行主流程
        return str(exc)[:500]


async def send_test(db, user_id: int, channel_id: int) -> Dict[str, Any]:
    channel = await dao.get_owned_channel_async(db, user_id, channel_id)
    if not channel:
        raise NotFound("通知通道不存在")
    error = await _send_to_channel(channel, "测试通知", "这是一条来自 AI 助手工作台的测试消息，收到即说明通道配置正确。")
    await dao.mark_sent_async(db, channel, error=error)
    if error:
        raise InvalidInput(f"发送失败：{error}")
    return {"message": "已发送，请检查接收端"}


async def dispatch_alert_async(db, user_id: int, *, title: str, message: str) -> None:
    """把一条告警推给用户所有启用的通道。全程 best-effort：任何失败只记日志，不抛异常——

    一次组件运行不能因为推送失败而被判定失败，用户也不该因为群机器人临时抽风而看到组件报错。
    """
    try:
        channels = await dao.list_enabled_channels_async(db, user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"读取通知通道失败: user_id={user_id}, error={exc}")
        return
    if not channels:
        return
    for channel in channels:
        error = await _send_to_channel(channel, title, message)
        if error:
            logger.warning(f"告警推送失败: channel_id={channel.id}, user_id={user_id}, error={error}")
        try:
            await dao.mark_sent_async(db, channel, error=error)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"记录推送结果失败: channel_id={channel.id}, error={exc}")
