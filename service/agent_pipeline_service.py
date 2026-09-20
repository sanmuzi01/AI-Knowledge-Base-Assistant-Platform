"""Agent 流水线：把多个 Agent 串成一条固定顺序的处理链。

范围有意收窄成"线性串行"：上一步的回答自动作为下一步的输入消息，不做分支/条件/
并行——那些是真正工作流引擎的复杂度，多数人的诉求其实是"先用 A 处理一遍，
再让 B 精加工"这种简单串联，值不值得上完整 DAG 编排，等有真实需求信号再说。

每一步都走和 `/chat/{id}` 完全一样的 chat_service.chat_with_agent，所以配额检查、
Token 记账、会话历史这些都是"免费"复用的——流水线不是绕开聊天主链路的另一套逻辑，
只是按顺序多调几次。正因为每步都要检查配额，一个用完配额的用户不能靠"分成流水线
的好几步"绕过限制。
"""
import json
from typing import Any, Dict, List, Optional

from service import chat_service, quota_service
from service.access_control import get_owned_agent_async
from service.exceptions import InvalidInput, NotFound, QuotaExceeded

_MIN_STEPS = 2
_MAX_STEPS = 10


def _pipeline_to_dict(pipeline) -> Dict[str, Any]:
    try:
        steps = json.loads(pipeline.steps_json)
    except (TypeError, ValueError):
        steps = []
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "steps": steps,
        "is_enabled": bool(pipeline.is_enabled),
        "created_at": pipeline.created_at.strftime("%Y-%m-%d %H:%M:%S") if pipeline.created_at else None,
        "updated_at": pipeline.updated_at.strftime("%Y-%m-%d %H:%M:%S") if pipeline.updated_at else None,
    }


async def _validate_steps(db, user_id: int, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(steps, list) or not (_MIN_STEPS <= len(steps) <= _MAX_STEPS):
        raise InvalidInput(f"流水线需要 {_MIN_STEPS}~{_MAX_STEPS} 个步骤")
    cleaned = []
    for i, step in enumerate(steps):
        agent_id = step.get("agent_id") if isinstance(step, dict) else None
        if not agent_id:
            raise InvalidInput(f"第 {i + 1} 步缺少 agent_id")
        agent = await get_owned_agent_async(db, user_id, int(agent_id))
        if not agent:
            raise InvalidInput(f"第 {i + 1} 步选的助手不存在或不属于你")
        label = str(step.get("label") or "").strip()[:60]
        cleaned.append({"agent_id": agent.id, "label": label or agent.name})
    return cleaned


async def list_pipelines_async(db, user_id: int) -> List[Dict[str, Any]]:
    from models.agent_pipeline_async_dao import list_pipelines_by_user_async

    pipelines = await list_pipelines_by_user_async(db, user_id)
    return [_pipeline_to_dict(p) for p in pipelines]


async def create_pipeline_async(
        db, user_id: int, name: str, description: Optional[str], steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from models.agent_pipeline_async_dao import create_pipeline_async as dao_create

    name = (name or "").strip()
    if not name:
        raise InvalidInput("请填写流水线名称")
    cleaned_steps = await _validate_steps(db, user_id, steps)
    pipeline = await dao_create(db, user_id, name, (description or "").strip() or None, cleaned_steps)
    return _pipeline_to_dict(pipeline)


async def update_pipeline_async(db, user_id: int, pipeline_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    from models.agent_pipeline_async_dao import get_owned_pipeline_async, update_pipeline_async as dao_update

    pipeline = await get_owned_pipeline_async(db, user_id, pipeline_id)
    if not pipeline:
        raise NotFound("流水线不存在")
    fields: Dict[str, Any] = {}
    if "name" in patch and (patch["name"] or "").strip():
        fields["name"] = patch["name"].strip()
    if "description" in patch:
        fields["description"] = (patch["description"] or "").strip() or None
    if "steps" in patch and patch["steps"] is not None:
        fields["steps_json"] = json.dumps(await _validate_steps(db, user_id, patch["steps"]), ensure_ascii=False)
    if "is_enabled" in patch and patch["is_enabled"] is not None:
        fields["is_enabled"] = 1 if patch["is_enabled"] else 0
    if not fields:
        raise InvalidInput("没有需要更新的内容")
    pipeline = await dao_update(db, pipeline, fields)
    return _pipeline_to_dict(pipeline)


async def delete_pipeline_async(db, user_id: int, pipeline_id: int) -> Dict[str, Any]:
    from models.agent_pipeline_async_dao import delete_pipeline_async as dao_delete, get_owned_pipeline_async

    pipeline = await get_owned_pipeline_async(db, user_id, pipeline_id)
    if not pipeline:
        raise NotFound("流水线不存在")
    await dao_delete(db, pipeline)
    return {"message": "流水线已删除", "id": pipeline_id}


async def run_pipeline_async(db, user, pipeline_id: int, initial_message: str) -> Dict[str, Any]:
    """按顺序跑完流水线的每一步，某一步失败就停在那一步——不让后面步骤继续消耗配额。"""
    from models.agent_pipeline_async_dao import get_owned_pipeline_async

    pipeline = await get_owned_pipeline_async(db, user.id, pipeline_id)
    if not pipeline:
        raise NotFound("流水线不存在")
    if not pipeline.is_enabled:
        raise InvalidInput("这条流水线已停用")

    try:
        steps = json.loads(pipeline.steps_json)
    except (TypeError, ValueError):
        steps = []
    if not steps:
        raise InvalidInput("流水线没有配置步骤")

    # 固化成普通值，理由同下面 agent.id/agent.name 那处注释：调用链里任何一次
    # db.rollback() 都会让这个对象过期，await 之后再读 ORM 属性会在 async 上下文
    # 里触发同步隐式刷新，报 MissingGreenlet。
    pipeline_id, pipeline_name = pipeline.id, pipeline.name

    message = initial_message
    step_results: List[Dict[str, Any]] = []
    for i, step in enumerate(steps):
        agent_id = step.get("agent_id")
        agent = await get_owned_agent_async(db, user.id, agent_id)
        if not agent:
            step_results.append({
                "step": i + 1, "agent_id": agent_id, "label": step.get("label"),
                "ok": False, "error": "该步骤的助手已被删除或不属于你",
            })
            break
        # 固化成普通值：chat_with_agent 内部失败路径可能 db.rollback()，
        # rollback 会让这个 session 关联的所有 ORM 对象过期（不受 expire_on_commit=False
        # 影响，那个开关只管 commit），之后再读 agent.name 会在 async 上下文里触发
        # 同步的隐式刷新，报 MissingGreenlet——和 agent_runtime.py 里 run_id 那处
        # "异常路径 rollback 会 expire run，之后不能再读 run.id" 是同一类坑。
        agent_id, agent_name = agent.id, agent.name

        try:
            quota_before = await quota_service.enforce_quota_async(db, user.id)
        except QuotaExceeded as e:
            step_results.append({
                "step": i + 1, "agent_id": agent_id, "agent_name": agent_name,
                "label": step.get("label"), "ok": False, "error": str(e),
            })
            break

        result = await chat_service.chat_with_agent(
            db=db, user=user, agent_id=agent_id, user_message=message,
        )
        await quota_service.check_and_notify_threshold_async(db, user.id, quota_before["used_tokens"])

        if "message" in result and "answer" not in result:
            step_results.append({
                "step": i + 1, "agent_id": agent_id, "agent_name": agent_name,
                "label": step.get("label"), "ok": False, "error": result["message"],
            })
            break

        answer = result.get("answer", "") or ""
        step_results.append({
            "step": i + 1, "agent_id": agent_id, "agent_name": agent_name,
            "label": step.get("label"), "ok": True,
            "question": message, "answer": answer,
            "conversation_id": result.get("conversation_id"),
        })
        message = answer

    return {
        "pipeline_id": pipeline_id,
        "pipeline_name": pipeline_name,
        "completed": all(s["ok"] for s in step_results) and len(step_results) == len(steps),
        "steps": step_results,
        "final_answer": step_results[-1]["answer"] if step_results and step_results[-1]["ok"] else None,
    }
