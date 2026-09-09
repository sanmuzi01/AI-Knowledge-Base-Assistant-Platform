"""
Agent Runtime - 智能体推理引擎
职责：接收用户消息 → 编排RAG/LLM → 记录运行轨迹 → 返回回答
这一层是"大脑"，chat_service只负责"传话"，不关心内部怎么编排。
架构位置：
  chat_service.py（传话层）
        ↓ 调用
  agent_runtime.py（编排层 ← 你在这里）
        ↓ 调用
  rag_service + llm_service + agent_run_dao
        ↓
  ChromaDB + 智谱API + MySQL
"""
from utils.timeutil import utcnow
from typing import Any, Dict, List
from datetime import datetime
from models.agent_run_dao import create_run, create_step, update_run_status
from service.access_control import get_owned_agent
from prompt.prompt_manager import build_prompt
from utils.logger_handler import get_logger
from service.runtime.sse_events import (
    make_ready, make_done, make_error, make_retrieval, make_memory, make_citations,
)
from typing import Generator
from service.memory.memory_service import load_memory, should_summarize, summarize_and_save
from service.user_profile_service import format_user_profile_for_prompt
# ========== 新增: ReAct 模式 ==========
from service.tools.executor import ToolExecutor
logger = get_logger("agent_runtime")

def _short_text(value: Any, limit: int = 1000) -> str:
    import json

    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    return text[:limit]


def _format_rag_audit(results: List[Dict[str, Any]], rag_context: str) -> str:
    import json

    payload = {
        "hit_count": len(results or []),
        "hits": [
            {
                "knowledge_id": item.get("knowledge_id"),
                "file_name": item.get("file_name") or (item.get("source") or {}).get("file_name"),
                "space_name": (item.get("source") or {}).get("space_name"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
                "rerank_score": item.get("rerank_score"),
                "distance": item.get("distance"),
                "content_preview": (item.get("content") or "")[:500],
            }
            for item in (results or [])
        ],
        "context_preview": rag_context[:1000],
    }
    return json.dumps(payload, ensure_ascii=False)


def _kb_retrieve(agent, user_id: int, agent_id: int, user_message: str) -> Dict[str, Any]:
    """统一 RAG 检索：绑定了知识库空间走多空间联合检索（带来源），否则走旧 Agent 私有库。

    返回 {context, citations, hit_count, mode, refused, error}。异常降级为空。
    """
    from service.rag import search_entry

    try:
        res = search_entry.search_for_agent(
            user_id, agent_id, user_message,
            top_k=int(getattr(agent, "kb_top_k", 5) or 5),
            rerank=bool(getattr(agent, "kb_rerank_enabled", 0)),
            refuse_when_empty=bool(getattr(agent, "kb_refuse_when_empty", 1)),
        )
        return {
            "context": res.get("context", ""),
            "citations": res.get("citations", []),
            "hit_count": len(res.get("hits", [])),
            "hits": res.get("hits", []),
            "mode": res.get("mode", "agent"),
            "refused": bool(res.get("refused")),
            "error": "",
        }
    except Exception as e:  # noqa: BLE001 —— RAG 失败一律降级，不阻断对话
        logger.warning(f"RAG 检索失败（降级跳过）: {e}")
        return {"context": "", "citations": [], "hit_count": 0, "hits": [],
                "mode": "error", "refused": False, "error": str(e)}


def _compose_kb_prompt(system_prompt: str, agent, rag: Dict[str, Any]) -> str:
    """把检索上下文 + 引用/拒答规则拼进 system prompt。"""
    context = rag.get("context") or ""
    if context:
        rules = ["若参考资料不足以回答问题，请如实说明，不要编造。"]
        if getattr(agent, "kb_force_citation", 1):
            rules.append("引用规则：回答中每处引用了下面资料的内容，都要在句末用【来源N】标注（N 为资料编号）。")
        return (
            f"{system_prompt}\n\n"
            f"=== 知识库参考资料（按编号）===\n{context}\n=== 参考资料结束 ===\n"
            + "\n".join(rules)
        )
    if getattr(agent, "rag_enabled", 0) and getattr(agent, "kb_refuse_when_empty", 1):
        return (
            f"{system_prompt}\n\n"
            f"注意：知识库中没有检索到与该问题相关的资料。"
            f"请直接告知用户「知识库中没有相关内容」，不要凭常识或推测作答。"
        )
    return system_prompt


def _compose_system_prompt(db, user_id: int, agent_id: int, agent) -> Dict[str, str]:
    """统一组装 Agent 基础提示词、用户画像和长期记忆。"""
    base_prompt = build_prompt(agent_id) or "你是一个通用智能助理。"

    profile_text = ""
    try:
        profile_text = format_user_profile_for_prompt(db, user_id) or ""
        if profile_text:
            logger.info(f"已加载用户画像，长度={len(profile_text)}")
    except Exception as profile_err:
        logger.warning(f"加载用户画像失败（降级跳过）: {profile_err}")

    memory_text = ""
    memory_error = ""
    if agent.memory_enabled:
        try:
            memory_text = load_memory(db, user_id, agent_id) or ""
            if memory_text:
                logger.info(f"已加载长期记忆，长度={len(memory_text)}")
        except Exception as mem_err:
            memory_error = str(mem_err)
            logger.warning(f"加载长期记忆失败（降级跳过）: {mem_err}")

    system_prompt = "\n\n".join([part for part in [base_prompt, profile_text, memory_text] if part])
    return {
        "system_prompt": system_prompt,
        "base_prompt": base_prompt,
        "profile_text": profile_text,
        "memory_text": memory_text,
        "memory_error": memory_error,
    }


def _record_react_step(db, run_id: int, step_no_ref: Dict[str, int], step_info: Dict[str, Any],
                       agent, user_message: str, rag_context: str):
    step_type = step_info.get("step_type", "thought")
    if step_type == "thought":
        tool_calls = step_info.get("tool_calls") or []
        if tool_calls:
            for tc in tool_calls:
                create_step(
                    db=db,
                    run_id=run_id,
                    step_no=step_no_ref["value"],
                    step_type="tool_call",
                    thought=_short_text(step_info.get("content"), 500),
                    tool_name=tc.get("name", ""),
                    tool_args=_short_text(tc.get("args", ""), 1000),
                    tool_result="",
                )
                step_no_ref["value"] += 1
        else:
            create_step(
                db=db,
                run_id=run_id,
                step_no=step_no_ref["value"],
                step_type="responder",
                thought=f"基于{'RAG上下文+' if rag_context else ''}ReAct引擎生成回答",
                tool_name=agent.model_name,
                tool_args=_short_text(user_message, 300),
                tool_result=_short_text(step_info.get("content"), 1200),
            )
            step_no_ref["value"] += 1
    elif step_type == "tool_result":
        permission_denied = bool(step_info.get("permission_denied"))
        create_step(
            db=db,
            run_id=run_id,
            step_no=step_no_ref["value"],
            step_type="permission_denied" if permission_denied else "tool_result",
            thought="工具权限拒绝" if permission_denied else "工具执行结果",
            tool_name=step_info.get("tool_name", ""),
            tool_args="",
            tool_result=_short_text(step_info.get("tool_result"), 2000),
        )
        step_no_ref["value"] += 1
    db.flush()


# 旧的 run() / run_stream()（旧 Chat 表路径）已删除——无调用方。
# 当前只有 *_with_history 版本，由 chat_service 调用。


async def run_with_history(
        db, user_id: int, agent_id: int, user_message: str,
        history: List[Dict[str, str]] = None,
        conversation_id: int = None,
) -> Dict[str, Any]:
    """同步执行（支持外部传入历史消息 + 关联会话）
    和 run() 的区别：
      - history 由调用方（chat_service）传入，不再从旧 Chat 表查
      - conversation_id 写入 AgentRun，便于按会话查运行记录
      - 不再调 create_chat 保存到旧表（由 chat_service 保存到 Message 表）
    """
    # 1. 查 Agent 配置
    agent = get_owned_agent(db, user_id, agent_id)
    if not agent:
        raise ValueError("智能体不存在或不属于当前用户")

    # 2. 创建 AgentRun（关联 conversation_id）
    run = create_run(
        db=db, user_id=user_id, agent_id=agent_id,
        user_message=user_message, conversation_id=conversation_id,
    )
    db.flush()
    logger.info(
        f"Agent运行开始: run_id={run.id}, agent_id={agent_id}, conv={conversation_id}, "
        f"rag={'on' if agent.rag_enabled else 'off'}, "
        f"memory={'on' if agent.memory_enabled else 'off'}"
    )

    try:
        # 3. system_prompt + Memory + RAG（和 run() 完全一致）
        prompt_parts = _compose_system_prompt(db, user_id, agent_id, agent)
        system_prompt = prompt_parts["system_prompt"]

        # RAG 检索：绑定知识库空间→多空间联合检索（带来源）；否则→旧 Agent 私有库。失败一律降级。
        rag = {"context": "", "citations": [], "hit_count": 0, "hits": [], "mode": "off",
               "refused": False, "error": ""}
        citations: List[Dict[str, Any]] = []
        if agent.rag_enabled:
            import asyncio
            logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
            rag = await asyncio.to_thread(_kb_retrieve, agent, user_id, agent_id, user_message)
            citations = rag.get("citations", [])
            if rag["error"]:
                thought, audit = f"RAG检索异常，已降级跳过: {rag['error'][:100]}", "检索失败，已跳过"
            elif rag["hit_count"]:
                thought = f"检索到{rag['hit_count']}条相关片段（{rag['mode']}）"
                audit = _format_rag_audit(rag["hits"], rag["context"])
            else:
                thought, audit = "知识库中未检索到相关内容", "无匹配结果"
            create_step(
                db=db, run_id=run.id, step_no=1, step_type="retrieval",
                thought=thought, tool_name="rag_search",
                tool_args=user_message[:200], tool_result=audit,
            )
        else:
            logger.info("RAG未启用，跳过知识库检索")

        rag_context = rag["context"]
        full_system_prompt = _compose_kb_prompt(system_prompt, agent, rag)

        # 4. 历史消息：直接用传入的（不再从旧 Chat 表查）
        if history is None:
            history = []

        # 5. 创建 ReAct 引擎（和 run() 一致）
        executor = ToolExecutor(
            db=db, user_id=user_id, agent_id=agent_id,
            model_name=agent.model_name,
            temperature=agent.temperature / 100,
        )
        step_no_ref = {"value": 2 if agent.rag_enabled else 1}

        def write_step(step_info):
            _record_react_step(db, run.id, step_no_ref, step_info, agent, user_message, rag_context)

        engine = executor.create_engine(max_iterations=5, step_callback=write_step)

        # 6. 执行 ReAct
        react_result = engine.invoke(
            system_prompt=full_system_prompt,
            user_message=user_message,
            history=history,
        )
        answer = react_result["answer"]

        # 7. 更新 AgentRun 状态（不调 create_chat，由 chat_service 保存消息）
        step_no = step_no_ref["value"] - 1 if step_no_ref["value"] > 1 else 1
        total_steps = step_no
        update_run_status(
            db=db, run=run, status="finished",
            final_answer=answer, total_steps=total_steps,
        )
        db.flush()

        # 8. 记忆总结（降级）
        if agent.memory_enabled:
            try:
                if should_summarize(db, user_id, agent_id):
                    logger.info("开始总结长期记忆...")
                    summarize_and_save(db, user_id, agent_id, agent.model_name)
                    db.flush()
                    logger.info("长期记忆总结完成")
            except Exception as mem_err:
                logger.warning(f"记忆总结失败（不影响对话结果）: {mem_err}")
                db.rollback()

        logger.info(f"Agent运行完成: run_id={run.id}, steps={total_steps}, answer长度={len(answer)}")
        return {
            "answer": answer,
            "run_id": run.id,
            "steps": total_steps,
            "question": user_message,
            "agent_id": agent_id,
            "citations": citations,
            "rag_mode": rag.get("mode", "off"),
            "rag_refused": rag.get("refused", False),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Agent运行失败: run_id={run.id}, error={e}")
        try:
            from models.init_db import AgentRun
            run_record = db.query(AgentRun).filter(AgentRun.id == run.id).first()
            if run_record:
                run_record.status = "failed"
                run_record.error_msg = str(e)[:500]
                run_record.finished_at = utcnow()
                db.commit()
        except Exception:
            db.rollback()
        raise

def run_stream_with_history(
        db, user_id: int, agent_id: int, user_message: str,
        history: List[Dict[str, str]] = None,
        conversation_id: int = None,
) -> Generator[str, None, None]:
    """流式执行（支持外部传入历史消息 + 关联会话）
    和 run_stream() 的区别：
      - history 由调用方传入
      - conversation_id 写入 AgentRun
      - 不再调 create_chat（由 chat_service 保存消息）
    """
    # 1. 查 Agent 配置
    try:
        agent = get_owned_agent(db, user_id, agent_id)
        if not agent:
            yield make_error("智能体不存在或不属于当前用户")
            return
    except Exception as e:
        yield make_error(f"查询智能体失败: {e}")
        return

    # 2. 创建 AgentRun（关联 conversation_id）
    try:
        run = create_run(
            db=db, user_id=user_id, agent_id=agent_id,
            user_message=user_message, conversation_id=conversation_id,
        )
        db.flush()
        logger.info(
            f"Agent[stream] 运行开始: run_id={run.id}, agent_id={agent_id}, "
            f"conv={conversation_id}, "
            f"rag={'on' if agent.rag_enabled else 'off'}, "
            f"memory={'on' if agent.memory_enabled else 'off'}"
        )
        yield make_ready(run.id)
    except Exception as e:
        yield make_error(f"创建运行记录失败: {e}")
        return

    try:
        # 3. system_prompt + Memory + RAG（和 run_stream 一致）
        prompt_parts = _compose_system_prompt(db, user_id, agent_id, agent)
        system_prompt = prompt_parts["system_prompt"]
        if prompt_parts["memory_text"]:
            yield make_memory("loaded", f"加载长期记忆 {len(prompt_parts['memory_text'])} 字")
        if prompt_parts["memory_error"]:
            yield make_memory("error", f"加载记忆失败，已跳过: {prompt_parts['memory_error'][:100]}")

        # RAG 检索：绑定知识库空间→多空间联合检索（带来源）；否则→旧 Agent 私有库。失败一律降级。
        rag = {"context": "", "citations": [], "hit_count": 0, "hits": [], "mode": "off",
               "refused": False, "error": ""}
        if agent.rag_enabled:
            logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
            rag = _kb_retrieve(agent, user_id, agent_id, user_message)
            if rag["error"]:
                thought, audit = f"RAG检索异常，已降级跳过: {rag['error'][:100]}", "检索失败，已跳过"
                yield make_retrieval(hit_count=0, content_preview=f"检索异常已跳过: {rag['error'][:100]}")
            elif rag["hit_count"]:
                thought = f"检索到{rag['hit_count']}条相关片段（{rag['mode']}）"
                audit = _format_rag_audit(rag["hits"], rag["context"])
                yield make_retrieval(hit_count=rag["hit_count"], content_preview=rag["context"])
            else:
                thought, audit = "知识库中未检索到相关内容", "无匹配结果"
                yield make_retrieval(hit_count=0, content_preview="知识库无匹配内容")
            create_step(
                db=db, run_id=run.id, step_no=1, step_type="retrieval",
                thought=thought, tool_name="rag_search",
                tool_args=user_message[:200], tool_result=audit,
            )
            if rag["citations"]:
                yield make_citations(rag["citations"])
        else:
            logger.info("RAG未启用，跳过知识库检索")

        rag_context = rag["context"]
        full_system_prompt = _compose_kb_prompt(system_prompt, agent, rag)

        # 4. 历史消息：用传入的
        if history is None:
            history = []

        # 5. 创建 ReAct 引擎
        executor = ToolExecutor(
            db=db, user_id=user_id, agent_id=agent_id,
            model_name=agent.model_name,
            temperature=agent.temperature / 100,
        )
        step_no_ref = {"value": 2 if agent.rag_enabled else 1}

        def write_step(step_info):
            _record_react_step(db, run.id, step_no_ref, step_info, agent, user_message, rag_context)

        engine = executor.create_engine(max_iterations=5, step_callback=write_step)

        # 6. 流式执行 ReAct
        stream_gen = engine.invoke_stream(
            system_prompt=full_system_prompt,
            user_message=user_message,
            history=history,
        )
        try:
            while True:
                event = next(stream_gen)
                yield event
        except StopIteration as si:
            react_result = si.value

        answer = react_result.get("answer", "") or ""
        step_no = step_no_ref["value"] - 1 if step_no_ref["value"] > 1 else 1
        total_steps = step_no

        # 7. 更新 AgentRun 状态（不调 create_chat）
        update_run_status(
            db=db, run=run, status="finished",
            final_answer=answer, total_steps=total_steps,
        )
        db.flush()

        # 8. 记忆总结
        if agent.memory_enabled:
            try:
                if should_summarize(db, user_id, agent_id):
                    logger.info("开始总结长期记忆...")
                    summarize_and_save(db, user_id, agent_id, agent.model_name)
                    db.flush()
                    yield make_memory("summarized", "长期记忆总结完成")
                    logger.info("长期记忆总结完成")
            except Exception as mem_err:
                logger.warning(f"记忆总结失败（不影响对话结果）: {mem_err}")
                yield make_memory("error", f"记忆总结失败: {str(mem_err)[:100]}")
                db.rollback()

        logger.info(
            f"Agent[stream] 运行完成: run_id={run.id}, steps={total_steps}, "
            f"answer长度={len(answer)}"
        )
        yield make_done(run.id, total_steps, len(answer))

    except Exception as e:
        db.rollback()
        logger.error(f"Agent[stream] 运行失败: run_id={run.id}, error={e}")
        try:
            from models.init_db import AgentRun
            run_record = db.query(AgentRun).filter(AgentRun.id == run.id).first()
            if run_record:
                run_record.status = "failed"
                run_record.error_msg = str(e)[:500]
                run_record.finished_at = utcnow()
                db.commit()
        except Exception:
            db.rollback()
        yield make_error(
            message="服务暂时异常，请稍后重试",
            detail=str(e)[:300]
        )
        return
