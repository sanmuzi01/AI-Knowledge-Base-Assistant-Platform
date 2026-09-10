"""数据源：联网检索。

平台没有现成数据源、用户也没给接口地址时用这个——直接让「用户已配置的、支持联网的
聊天模型」（智谱 / 通义 / Kimi / OpenAI search-preview / Perplexity）去查，
把结果抠成结构化数据。用户不用另配 key（除非只配了 DeepSeek 这种不带联网的）。

时序说明：搜索型模型给的是「当前值 + 来源」，补不出准确的历史。所以「走势」靠组件
每次运行把一个数据点攒起来形成（平台已有 data-point 保留机制）。

输出里始终带 `summary`（一段 markdown）：查到就是「值 + 日期 + 来源 + 用的模型」，
查不到就说清楚原因和替代做法。所以 web_query 组件默认用 markdown 视图——即使没抠出
数字也有东西可看，不会只显示「还没有数据」。有数字时另给 value / rows 供 metric / chart 用。

config:
  - query:  必填，要查什么（把主题写全，例如「三角洲行动 7.62mm 子弹 交易行价格」）
  - model:  选填，指定用哪个已配置模型；默认自动挑一个支持联网的
"""

import json
import re
from typing import Any, Dict, List

from utils.logger_handler import get_logger
from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext

logger = get_logger("widget_web_query_connector")

_SYSTEM = (
    "你是联网数据助手。用户给一个要查的指标，你联网查最新信息，只输出一个 JSON 对象，"
    "不要任何解释或 markdown 代码块。\n"
    "只要联网找到了**任何相关的当前信息**就算查到（found=true）：\n"
    '  {"found": true, "value": <能给出数字就给数字，否则给一句简短中文>, '
    '"unit": "<单位，可空>", "as_of": "<YYYY-MM-DD 数据对应日期，不确定就填今天>", '
    '"note": "<补充说明，例如是区间/估算/涨跌，可空>", "sources": ["<参考网址>", ...]}\n'
    "只有联网后**确实什么相关信息都没有**，才 found=false：\n"
    '  {"found": false, "reason": "<中文说明为什么查不到，例如没有公开数据/需要登录/只有历史数据>"}\n'
    "可以给近似值或区间（在 note 里说明），但不要凭空编造具体数字或网址。"
)

# 「值本身就是个数」才当数字：纯数字，或数字 + 短单位/货币符号。
# 整句话里埋了个数字（"1800~2000 之间波动"）不算——那种当文本，不进图表。
_PURE_NUM_RE = re.compile(r"^\s*[$€£¥]?\s*-?[\d,]+\.?\d*\s*[^\d\s]{0,6}\s*$")
_NUM_RE = re.compile(r"-?[\d,]+\.?\d*")


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
    a, b = s.find("{"), s.rfind("}")
    if a == -1 or b <= a:
        return {}
    try:
        obj = json.loads(s[a:b + 1])
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def _to_number(value: Any):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value or "")
    if not _PURE_NUM_RE.match(s):
        return None  # 是一句话，不是一个数
    m = _NUM_RE.search(s)
    try:
        return float(m.group(0).replace(",", "")) if m else None
    except ValueError:
        return None


class WebQueryConnector(BaseConnector):
    kind = "web_query"
    label = "联网检索"
    needs_db = True  # 要按用户读其已配置的模型 / key

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        config = config or {}
        errors: List[str] = []
        if not str(config.get("query") or "").strip():
            errors.append("请填写要联网查什么（query）")
        model = config.get("model")
        if model is not None and not str(model).strip():
            errors.append("model 不能是空字符串")
        return errors

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        from service.exceptions import UpstreamError
        from service.llm.factory import LLMFactory
        from service.llm.web_search import resolve_search_model_async

        config = config or {}
        query = str(config.get("query") or "").strip()
        preferred = str(config.get("model") or "").strip() or None

        if ctx.db is None:
            raise UpstreamError("联网检索需要数据库上下文")

        resolved = await resolve_search_model_async(ctx.db, ctx.user_id, preferred)
        if not resolved:
            raise UpstreamError(
                "你的模型不支持联网检索。请在【连接模型】里配置智谱 / 通义千问 / Kimi / "
                "Perplexity 之一（都能用同一个 Key 联网）。"
            )
        model_name, api_key, api_url = resolved
        client = LLMFactory.create(model_name, api_key, api_url)

        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"联网查：{query}"},
        ]
        try:
            answer = await client.achat(messages, temperature=0, web_search=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"web_query 调模型失败: user_id={ctx.user_id}, model={model_name}, error={exc}")
            raise UpstreamError(f"联网检索没成功：{str(exc)[:200]}") from exc

        parsed = _extract_json(answer)
        fetched_at = ctx.now.strftime("%Y-%m-%d %H:%M:%S")
        found = bool(parsed.get("found"))
        result: Dict[str, Any] = {
            "query": query,
            "model": model_name,
            "found": found,
            "fetched_at": fetched_at,
            "raw": answer[:2000],
        }

        if not found:
            reason = str(parsed.get("reason") or "").strip() or "联网后没找到相关的当前信息"
            result["reason"] = reason
            result["rows"] = []
            # markdown 视图始终有东西可显示：说清楚为什么没查到 + 怎么办
            result["summary"] = (
                f"**没查到「{query}」**\n\n{reason}\n\n"
                f"> 用的是 {model_name}。可以换一个联网更强的模型（Perplexity `sonar` 通常最稳），"
                f"或改用「调用我的接口」填一个能返回该数据的地址。"
            )
            return result

        value = parsed.get("value")
        number = _to_number(value)
        as_of = str(parsed.get("as_of") or "").strip() or ctx.now.strftime("%Y-%m-%d")
        unit = str(parsed.get("unit") or "").strip()
        note = str(parsed.get("note") or "").strip()
        sources = [str(u) for u in (parsed.get("sources") or []) if str(u).strip()][:5]

        head = f"{number:g}" if number is not None else str(value)
        lines = [f"**{head}{(' ' + unit) if unit else ''}**  ·  {query}"]
        if as_of:
            lines.append(f"数据日期：{as_of}")
        if note:
            lines.append(note)
        if number is None:
            lines.append("_未抠出确定数字，仅供参考_")
        if sources:
            lines.append("来源：" + " · ".join(sources))
        lines.append(f"_联网检索 · 模型 {model_name} · {fetched_at}_")

        result.update({
            "value": value,
            "number": number,
            "unit": unit,
            "as_of": as_of,
            "note": note,
            "sources": sources,
            "low_confidence": number is None,
            "summary": "\n\n".join(lines),
            # 单点时序：多次运行累积成走势；normalize_timeseries 认 t / y
            "rows": [{"t": as_of, "y": number}] if number is not None else [],
        })
        return result


CONNECTOR = WebQueryConnector()
