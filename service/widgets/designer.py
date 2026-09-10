"""/design：把用户的自然语言需求解析成组件草稿配置。

- 用用户自己在【连接模型】里配置并启用的聊天模型（走用户自己的鉴权/计费/限流）。
- 未配置模型时返回中文提示，不报错。
- LLM 只被要求产出白名单内的 JSON；产出后一律过 validator 校验/归一，不直接信任。
- llm_call 可注入，便于脱离真实模型做单元测试。
"""

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

from utils.logger_handler import get_logger
from service.widgets import schema
from service.widgets.connectors.catalog import CATALOG_PROVIDERS
from service.widgets.validator import validate_and_normalize

logger = get_logger("widget_designer")

LlmCall = Callable[[List[Dict[str, str]]], Awaitable[str]]

NO_MODEL_MESSAGE = "请先连接 AI 服务：在【连接模型】里配置并启用一个聊天模型，然后再来创建组件。"


def _system_prompt(web_search_available: bool = False) -> str:
    provider_keys = ", ".join(CATALOG_PROVIDERS.keys())
    if web_search_available:
        rule6 = (
            '6. 以上都不满足（例如"三角洲子弹价格""某只股票走势""某加密货币行情"这类主题），\n'
            "   用户没给接口地址、也没说从知识库查 -> data_source.kind=web_query，\n"
            "   config.query 填「把用户要查的东西写完整，带上关键限定词」。系统会用用户已配置的联网模型去查。\n"
            "   web_query 固定配 type=markdown、view.kind=markdown、processor.kind=passthrough\n"
            "   （联网查到的是当前值 + 来源，展示成一段话最稳；即便用户说了折线图也先用 markdown，\n"
            "    走势要靠组件每天跑一次慢慢攒）。\n"
            "   —— 严禁用 gold_price / usd_cny / weather 或任何不相关数据源顶替，严禁编造接口地址。"
        )
    else:
        rule6 = (
            "6. 以上都不满足 -> **必须**输出，一个字都不要多：\n"
            '   {"needs_clarification": true, "question": "我暂时没有『<把用户要的主题填这里>』的现成数据源，'
            '你现在连接的模型也不支持联网检索。可以配一个支持联网的模型（智谱/通义/Kimi/Perplexity），'
            '或给我一个能返回该数据的接口地址(http/https)。"}\n'
            "   —— 严禁用 gold_price / usd_cny / weather 或任何不相关数据源顶替，严禁编造接口地址。"
        )
    return f"""你是工作台小组件的配置助手。用户用中文描述想要的小窗口，你只输出一个 JSON 对象，描述该组件的配置。严禁输出任何前端代码、脚本、SQL 或解释文字。

只能使用下列白名单取值：
- type: {", ".join(schema.WIDGET_TYPES)}
- data_source.kind: {", ".join(schema.CONNECTOR_KINDS)}
  - catalog 是**封闭清单**，config.provider 只有这三个取值: {provider_keys}
    （gold_price=黄金价格，usd_cny=美元兑人民币汇率，weather=天气）。没有别的 provider。
  - sample 用于演示，config 可含 series、points
  - system_stats / agent_runs 是"当前用户自己的"统计，无需额外 config
  - http 需要 config.url（http/https）；可选 config.method(GET/POST)、config.headers、config.json_path
  - web_page 需要 config.url；可选 config.mode（text 纯展示 / monitor 关注是否更新）
  - web_query 无现成数据源时用：config.query 必填（要联网查什么，写完整）。系统用用户已配置的联网模型去查
  - knowledge_base 需要 config.agent_id(数字) 和 config.query（检索问题）；可选 config.top_k
  - knowledge_space 需要 config.space_id(数字)，输出某知识库空间的健康分和文档/检索质量指标
- processor.kind: {", ".join(schema.PROCESSOR_KINDS)}
  - llm_summarize 用 AI 把取到的数据总结成有条理的一段 Markdown，配合 view.kind=markdown；
    可选 config.instruction、config.style（brief 结论+要点 / report 分小节 / one_line 一句话）
  - threshold_alert 按阈值判定 ok/warn/alert，配合 view.kind=metric 或 markdown；
    config 用简写 {{"gt": 100}} 或 {{"lt": 5}}，或 config.rules=[{{"level":"warn|alert","op":"gt|lt|gte|lte|eq","value":N,"message":"…"}}]，
    可加 config.field 指定比较哪个字段
- view.kind: {", ".join(schema.VIEW_KINDS)}；chart 的 config.chart_type 取值: {", ".join(schema.CHART_TYPES)}
- trigger.kind: {", ".join(schema.TRIGGER_KINDS)}；daily 需要 config.run_at(HH:MM) 和 config.timezone
- actions: {", ".join(schema.ACTIONS)}

映射规则：
- "每天/每日更新" -> trigger.kind=daily；"每小时" -> hourly；"手动/点一下刷新" -> manual
- "折线图" -> view.kind=chart, chart_type=line；"柱状图" -> bar；"饼图" -> pie
- "表格" -> table；"摘要/报告/文字" -> markdown；"指标/数字/卡片" -> metric
- "网页/监控某个页面" -> type=web_monitor, view.kind=web_monitor, data_source.kind=web_page
- "关注某网页有没有更新/变化" -> data_source.kind=web_page, config.mode=monitor
- "调用我自己的接口 / 某个 API 地址 / http 链接返回的数据" -> data_source.kind=http
- "从我的知识库 / 资料里查" -> data_source.kind=knowledge_base
- "知识库 / 知识空间 健康 / 质量 / 有没有过期失败" -> data_source.kind=knowledge_space（config.space_id）
- "总结 / 提炼 / 概括成一段话" -> processor.kind=llm_summarize + view.kind=markdown
- "超过 / 低于 X 就提醒 / 报警 / 预警" -> processor.kind=threshold_alert（把 X 放进 config）
- "我的运行/调用/Agent 统计" -> data_source.kind=agent_runs
- "系统状态/使用概览" -> data_source.kind=system_stats
- 时间序列 + 图表 -> processor.kind=normalize_timeseries
- 需要一个汇总数字 -> processor.kind=aggregate

确定数据来源的硬规则，**按顺序判断，命中即停**：
1. 用户给了 http/https 接口地址 -> data_source.kind=http（config.url 用用户给的地址；绝不自己编 URL）
2. 用户说"从我的知识库/资料里查" -> knowledge_base；"知识库/空间 健康/质量" -> knowledge_space
3. "我自己的运行/调用统计" -> agent_runs；"系统状态/使用概览" -> system_stats
4. "监控某网页/关注某页面有没有更新" -> web_page
5. 主题正好是黄金价格 / 美元人民币汇率 / 天气 之一 -> catalog，填对应 provider
{rule6}

如果连 type（图表/表格/文字/监控）都无法判断，同样输出 needs_clarification 追问。

否则输出组件配置，字段：name, type, description, data_source, processor, view, trigger, actions。
只输出 JSON，不要用 markdown 代码块包裹。"""


# catalog 是封闭的 3 个 provider。LLM 有时会把"三角洲子弹价格"这类没有数据源的主题
# 硬塞成 gold_price。兜底：选了 catalog 但用户原话里完全没提到该 provider 的主题 -> 打回追问。
_CATALOG_SUBJECT_HINTS = {
    "gold_price": ("黄金", "金价", "金子", "gold"),
    "usd_cny": ("汇率", "美元", "人民币", "美金", "外汇", "usd", "cny", "rmb", "兑"),
    "weather": ("天气", "气温", "温度", "气象", "下雨", "阴晴", "weather"),
}


def _catalog_subject_mismatch(prompt: str, spec: Dict[str, Any]) -> bool:
    ds = spec.get("data_source") or {}
    if ds.get("kind") != "catalog":
        return False
    provider = str((ds.get("config") or {}).get("provider") or "").strip()
    hints = _CATALOG_SUBJECT_HINTS.get(provider)
    if not hints:
        return True
    low = (prompt or "").lower()
    return not any(h.lower() in low for h in hints)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        return None


async def _web_search_available_async(db, user_id: int) -> bool:
    """用户是否配置了支持联网检索的聊天模型（决定 designer 是走 web_query 还是回退追问）。"""
    if db is None or not user_id:
        return False
    try:
        from service.llm.web_search import resolve_search_model_async
        return await resolve_search_model_async(db, user_id) is not None
    except Exception:  # noqa: BLE001 - 判断失败按"没有"处理
        return False


async def _default_llm_call_factory(db, user_id: int) -> Optional[LlmCall]:
    """返回一个可调用的 llm_call；用户没有可用聊天模型时返回 None。"""
    from service.llm.llm_config_service import async_get_api_config
    from service.llm.model_catalog import model_type
    from models.llm_config_async_dao import list_configs_by_user_async
    from service.llm.factory import LLMFactory

    configs = await list_configs_by_user_async(db, user_id)
    chat_models = [
        c.model_name for c in configs
        if c.is_active and model_type(c.model_name) == "chat"
    ]
    if not chat_models:
        return None
    model_name = chat_models[0]
    api_config = await async_get_api_config(db, user_id, model_name)
    if not api_config:
        return None
    client = LLMFactory.create(model_name, api_config["api_key"], api_config.get("api_url"))

    async def _call(messages: List[Dict[str, str]]) -> str:
        return await client.achat(messages, temperature=0)

    return _call


async def design_widget(db, user_id: int, prompt: str, *, llm_call: Optional[LlmCall] = None) -> Dict[str, Any]:
    """返回 {needs_clarification, message?, draft?, explain?}。"""
    text = (prompt or "").strip()
    if not text:
        return {"needs_clarification": True, "message": "请先用一句话描述你想要的小窗口，例如：每天看一次黄金价格走势折线图。"}

    web_search_available = await _web_search_available_async(db, user_id)

    if llm_call is None:
        llm_call = await _default_llm_call_factory(db, user_id)
        if llm_call is None:
            return {"needs_clarification": True, "message": NO_MODEL_MESSAGE, "reason": "no_model"}

    messages = [
        {"role": "system", "content": _system_prompt(web_search_available)},
        {"role": "user", "content": text},
    ]
    try:
        answer = await llm_call(messages)
    except Exception as exc:  # noqa: BLE001 - 模型调用失败给中文提示，不抛 500
        logger.warning(f"组件设计调用模型失败: user_id={user_id}, error={exc}")
        return {"needs_clarification": True, "message": "AI 服务暂时没有响应，请稍后再试一次。"}

    raw = _extract_json(answer)
    if raw is None:
        return {"needs_clarification": True, "message": "没太理解这个需求，换种说法再试试？比如说明数据来源、展示形式和更新频率。"}

    result = validate_and_normalize(raw)
    if result.needs_clarification:
        return {"needs_clarification": True, "message": result.message}
    if not result.ok:
        # LLM 产出越界字段：当作没问清楚，回中文追问
        return {"needs_clarification": True, "message": "这个需求我还差点信息，能再具体点吗？比如更新频率、想看成图表还是表格。"}

    if _catalog_subject_mismatch(text, result.spec):
        if web_search_available:
            rebuilt = dict(result.spec)
            rebuilt["data_source"] = {"kind": "web_query", "config": {"query": text[:300]}}
            # 联网检索单值展示成一段话最稳，不用 chart/metric（走势靠每天攒）
            rebuilt["type"] = "markdown"
            rebuilt["view"] = {"kind": "markdown", "config": {}}
            rebuilt["processor"] = {"kind": "passthrough", "config": {}}
            revalidated = validate_and_normalize(rebuilt)
            if revalidated.ok:
                logger.info(f"组件设计：catalog 主题不匹配，已改走联网检索, user_id={user_id}, prompt={text[:60]!r}")
                return {
                    "needs_clarification": False,
                    "draft": revalidated.spec,
                    "explain": schema.describe_spec(revalidated.spec),
                    "reason": "auto_web_query",
                }
        logger.info(f"组件设计：catalog 主题不匹配已打回, user_id={user_id}, prompt={text[:60]!r}")
        return {
            "needs_clarification": True,
            "message": "我暂时没有这个主题的现成数据源（内置只有黄金价格、美元人民币汇率、天气），"
                       "你连接的模型也不支持联网检索。可以配一个支持联网的模型（智谱/通义/Kimi/Perplexity），"
                       "或给我一个能返回该数据的接口地址(http/https)。",
            "reason": "no_data_source",
        }

    return {
        "needs_clarification": False,
        "draft": result.spec,
        "explain": schema.describe_spec(result.spec),
    }
