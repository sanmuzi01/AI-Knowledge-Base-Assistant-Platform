"""数据源：抓取一个网页的正文（P2）。

复用 web_crawler_service：出站前做 SSRF 校验、跟随重定向时逐跳校验、限制大小、
必要时用无头浏览器兜底。抓下来的正文既可以直接展示（markdown / web_monitor 视图），
也可以配合 mode=monitor 做「这个网页有没有更新」的监控——通过和上一次运行的
内容指纹比对得出 changed。

config:
  - url:       必填，http/https
  - mode:      "text"（默认，纯展示最近正文）/ "monitor"（关注是否变化）
  - max_chars: 正文最多保留多少字，默认 4000，范围 200~20000
"""

import asyncio
import hashlib
import json
import os
from typing import Any, Dict, List

from utils.logger_handler import get_logger
from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext

logger = get_logger("widget_web_page_connector")


def _default_max_chars() -> int:
    try:
        return int(os.getenv("WIDGET_WEBPAGE_MAX_CHARS", "4000"))
    except (TypeError, ValueError):
        return 4000


async def _previous_hash(ctx: WidgetRunContext) -> str:
    """取上一次运行落库的内容指纹，用于判断网页有没有变化。"""
    if ctx.db is None or ctx.widget_id is None:
        return ""
    try:
        from models import user_widget_async_dao as dao

        point = await dao.latest_data_point_async(ctx.db, ctx.widget_id)
        if not point or not point.payload_json:
            return ""
        payload = json.loads(point.payload_json)
        result = payload.get("result") if isinstance(payload, dict) else None
        if isinstance(result, dict):
            return str(result.get("content_hash") or "")
    except Exception as exc:  # noqa: BLE001 - 拿不到历史指纹不影响本次抓取
        logger.debug(f"读取网页历史指纹失败: widget_id={ctx.widget_id}, error={exc}")
    return ""


class WebPageConnector(BaseConnector):
    kind = "web_page"
    label = "网页内容"
    needs_db = True  # monitor 模式要读上一次的内容指纹

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        config = config or {}
        errors: List[str] = []
        url = str(config.get("url") or "").strip()
        if not url:
            errors.append("请填写要抓取的网页地址")
        elif not url.lower().startswith(("http://", "https://")):
            errors.append("网页地址必须以 http:// 或 https:// 开头")
        mode = str(config.get("mode") or "text").strip()
        if mode not in ("text", "monitor"):
            errors.append("网页数据源的模式只支持 text 或 monitor")
        max_chars = config.get("max_chars", _default_max_chars())
        if not isinstance(max_chars, int) or not (200 <= max_chars <= 20000):
            errors.append("网页正文保留字数需要在 200~20000 之间")
        return errors

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        from service.web_crawler_service import CrawlerError, crawl_url_to_markdown

        config = config or {}
        url = str(config.get("url") or "").strip()
        mode = str(config.get("mode") or "text").strip()
        max_chars = int(config.get("max_chars") or _default_max_chars())
        max_chars = max(200, min(max_chars, 20000))

        try:
            doc = await asyncio.to_thread(crawl_url_to_markdown, url)
        except CrawlerError as exc:
            from service.exceptions import UpstreamError
            raise UpstreamError(f"这个网页抓不了：{exc}") from exc

        content_bytes = doc.get("content") or b""
        full_text = content_bytes.decode("utf-8", errors="replace") if isinstance(content_bytes, bytes) else str(content_bytes)
        text = full_text.strip()
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        prev_hash = await _previous_hash(ctx) if mode == "monitor" else ""
        changed = bool(prev_hash) and prev_hash != content_hash

        return {
            "url": doc.get("url") or url,
            "title": doc.get("title") or "",
            "mode": mode,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
            "length": len(text),
            "content_hash": content_hash,
            "previous_hash": prev_hash,
            "changed": changed,
            "first_seen": not prev_hash,
            "fetched_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S"),
        }


CONNECTOR = WebPageConnector()
