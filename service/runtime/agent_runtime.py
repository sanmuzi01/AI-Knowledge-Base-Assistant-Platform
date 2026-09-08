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
from typing import Any, Dict, List
from datetime import datetime
from models.agent_run_dao import create_run, create_step, update_run_status
from models.chat_dao import create_chat, list_chats_by_agent
from service.access_control import get_owned_agent
from prompt.prompt_manager import build_prompt
from service.rag.rag_service import search as rag_search
from service.rag.rag_service import async_search as async_rag_search
from utils.logger_handler import get_logger
from service.runtime.sse_events import make_ready, make_done, make_error, make_retrieval, make_memory
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
                "file_name": item.get("file_name"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
                "distance": item.get("distance"),
                "content_preview": (item.get("content") or "")[:500],
            }
            for item in (results or [])
        ],
        "context_preview": rag_context[:1000],
    }
    return json.dumps(payload, ensure_ascii=False)


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


def run(
        db,user_id:int,agent_id:int,user_message:str
)->Dict[str,Any]:
    """
       Agent Runtime 的主入口：执行一次完整的推理流程
       流程：
         1. 查Agent配置
         2. 创建AgentRun记录（轨迹追踪）
         3. 如果RAG启用 → 检索知识库 → 拼进prompt
         4. 调LLM生成回答
         5. 更新AgentRun状态为finished
         6. 保存聊天记录
         7. 返回结果
       :param db: 数据库会话
       :param user_id: 用户ID
       :param agent_id: 智能体ID
       :param user_message: 用户消息
       :return: {"answer": str, "run_id": int, "steps": int}
       """
    #1.查Agent配置
    agent = get_owned_agent(db, user_id, agent_id)
    if not agent:
        raise ValueError("智能体不存在或不属于当前用户")
    #2.创建AgentRun记录（轨迹追踪）
    run = create_run(db = db,user_id = user_id,agent_id = agent_id,user_message = user_message)
    db.flush()
    logger.info(
        f"Agent运行开始: run_id={run.id}, agent_id={agent_id}, "
        f"rag={'on' if agent.rag_enabled else 'off'}, "
        f"memory={'on' if agent.memory_enabled else 'off'}"
    )
    #3.按开关编排：RAG/Memory 失败降级，不阻断主流程
    try:
        prompt_parts = _compose_system_prompt(db, user_id, agent_id, agent)
        system_prompt = prompt_parts["system_prompt"]

        # ====== RAG：开关控制 + 失败降级 ======
        rag_context = ""
        if agent.rag_enabled:
            step_no = 1
            try:
                logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
                results = rag_search(db, user_id, agent_id, user_message, top_k=3)
                if results:
                    rag_context = "\n\n".join([
                        f"[知识片段{i+1}]\n{r['content']}"
                        for i, r in enumerate(results)
                    ])
                    logger.info(f"RAG检索完成: 命中{len(results)}条")
                    create_step(
                        db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                        thought=f"用户问题需要知识库辅助，检索到{len(results)}条相关片段",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result=_format_rag_audit(results, rag_context)
                    )
                else:
                    logger.info("RAG检索无结果，将直接使用LLM回答")
                    create_step(
                        db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                        thought="知识库中未检索到相关内容",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result="无匹配结果",
                    )
            except Exception as rag_err:
                # RAG 失败不崩溃，降级为纯对话
                logger.warning(f"RAG检索失败（降级跳过，不使用知识库）: {rag_err}")
                rag_context = ""
                create_step(
                    db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                    thought=f"RAG检索异常，已降级跳过: {str(rag_err)[:100]}",
                    tool_name="rag_search", tool_args=user_message[:200],
                    tool_result="检索失败，已跳过",
                )
        else:
            logger.info("RAG未启用，跳过知识库检索")

        # 如果有RAG上下文，拼到system_prompt后面
        if rag_context:
            full_system_prompt =(
                f"{system_prompt}\n\n"
                f"=== 以下是从知识库检索到的参考资料，请基于这些内容回答用户问题 ===\n"
                f"{rag_context}\n"
                f"=== 参考资料结束 ===\n"
                f"注意：如果参考资料中没有相关信息，请如实告知用户。"
            )
        else:
            full_system_prompt = system_prompt

        # 查历史对话（最近10轮）
        history_chats = list_chats_by_agent(db,user_id,agent_id,limit=10)
        history = []
        for c in reversed(history_chats):
            history.append({"role": "user", "content": c.question})
            history.append({"role": "assistant", "content": c.answer})
        # 调用LLM
        # ========== ReAct 模式：用 LangGraph StateGraph 推理 ==========
        # 1.创建ToolExecutor（组装 LLM + 工具 + prompt）
        executor = ToolExecutor(
            db=db,
            user_id=user_id,
            agent_id=agent_id,
            model_name=agent.model_name,
            temperature=agent.temperature / 100,  # ← 新增
        )
        # 2.计算step_no起点（RAG启用=第2步开始，RAG未启用=第1步开始）
        step_no_ref = {"value": 2 if agent.rag_enabled else 1}
        # 3.每步回调：ReAct引擎每走一步就写一次轨迹到DB
        def write_step(step_info):
            """实时写轨迹到 AgentStep 表"""
            _record_react_step(db, run.id, step_no_ref, step_info, agent, user_message, rag_context)
        # 4.创建ReAct引擎
        engine = executor.create_engine(
            max_iterations=5,
            step_callback=write_step,
        )
        # 5.执行ReAct循环
        react_result = engine.invoke(
            system_prompt=full_system_prompt,
            user_message=user_message,
            history=history,
        )
        answer = react_result["answer"]
        # ReAct 内部已经记录了 thought/tool_call 步骤,step_no 继续往后加
        # 但 write_step 里已经+过了,所以这里直接取最终值即可
        step_no = step_no_ref["value"] - 1 if step_no_ref["value"] > 1 else 1
        #更新AgentRun状态为finished
        total_steps = step_no
        update_run_status(
            db=db,run=run,status="finished",final_answer=answer,
            total_steps=total_steps)
        #保存聊天记录
        chat = create_chat(db,user_id,agent_id,user_message,answer)
        db.commit()
        # 对话结束后，判断是否需要总结记忆（开关控制 + 失败降级）
        if agent.memory_enabled:
            try:
                if should_summarize(db, user_id, agent_id):
                    logger.info("开始总结长期记忆...")
                    summarize_and_save(db, user_id, agent_id, agent.model_name)
                    db.commit()
                    logger.info("长期记忆总结完成")
            except Exception as mem_err:
                logger.warning(f"记忆总结失败（不影响对话结果）: {mem_err}")
                db.rollback()
        else:
            logger.debug("Memory未启用，跳过记忆总结")
        logger.info(f"Agent运行完成: run_id={run.id}, steps={total_steps}, answer长度={len(answer)}")
        return {
            "answer": answer,#模型的最终回答
            "run_id": run.id,#执行任务的唯一编号
            "steps": total_steps,#执行过多少步骤
            "question": user_message,#用户的原始输入
            "agent_id": agent_id,
        }
    except Exception as e:
        # 出错了：回滚 + 记录失败状态
        db.rollback()
        logger.error(f"Agent运行失败: run_id={run.id}, error={e}")
        # 重新创建一个session来记录失败状态（因为上面rollback了）
        # 这里用run.id来更新
        try:
            from models.init_db import AgentRun
            run_record = db.query(AgentRun).filter(AgentRun.id ==run.id).first()
            if run_record:
                run_record.status = "failed"
                run_record.error_msg = str(e)[:500]
                run_record.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()

        raise
def run_stream(db, user_id: int, agent_id: int, user_message: str) -> Generator[str, None, None]:
    """流式执行一次推理（生成器，yield SSE 事件字符串）
        流程和 run() 完全一致，区别：
          - 每一步 yield SSE 事件（给前端实时推送）
          - 异常不 raise，转为 yield error 事件
          - 使用 ReAct 的 invoke_stream()，逐节点透传事件
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

        # 2. 创建 AgentRun 记录
    try:
        run = create_run(db=db, user_id=user_id, agent_id=agent_id, user_message=user_message)
        db.flush()
        logger.info(
            f"Agent[stream] 运行开始: run_id={run.id}, agent_id={agent_id}, "
            f"rag={'on' if agent.rag_enabled else 'off'}, "
            f"memory={'on' if agent.memory_enabled else 'off'}"
        )
        yield make_ready(run.id)
    except Exception as e:
        yield make_error(f"创建运行记录失败: {e}")
        return

        # 用 try 包裹完整流程，确保异常都转成 error 事件 + 记录 DB 失败状态
    try:
        # 3. 按开关编排（RAG/Memory 各自降级）
        prompt_parts = _compose_system_prompt(db, user_id, agent_id, agent)
        system_prompt = prompt_parts["system_prompt"]
        if prompt_parts["memory_text"]:
            yield make_memory("loaded", f"加载长期记忆 {len(prompt_parts['memory_text'])} 字")
        if prompt_parts["memory_error"]:
            yield make_memory("error", f"加载记忆失败，已跳过: {prompt_parts['memory_error'][:100]}")

        # ===== RAG：开关控制 + 失败降级 =====
        rag_context = ""
        if agent.rag_enabled:
            step_no_rag = 1
            try:
                logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
                results = rag_search(db, user_id, agent_id, user_message, top_k=3)
                if results:
                    rag_context = "\n\n".join([
                        f"[知识片段{i + 1}]\n{r['content']}"
                        for i, r in enumerate(results)
                    ])
                    logger.info(f"RAG检索完成: 命中{len(results)}条")
                    yield make_retrieval(
                        hit_count=len(results), content_preview=rag_context
                    )
                    create_step(
                        db=db, run_id=run.id, step_no=step_no_rag, step_type="retrieval",
                        thought=f"用户问题需要知识库辅助，检索到{len(results)}条相关片段",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result=_format_rag_audit(results, rag_context)
                    )
                else:
                    logger.info("RAG检索无结果")
                    yield make_retrieval(hit_count=0, content_preview="知识库无匹配内容")
                    create_step(
                        db=db, run_id=run.id, step_no=step_no_rag, step_type="retrieval",
                        thought="知识库中未检索到相关内容",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result="无匹配结果",
                    )
            except Exception as rag_err:
                logger.warning(f"RAG检索失败（降级跳过）: {rag_err}")
                yield make_retrieval(
                    hit_count=0, content_preview=f"检索异常已跳过: {str(rag_err)[:100]}"
                )
                create_step(
                    db=db, run_id=run.id, step_no=step_no_rag, step_type="retrieval",
                    thought=f"RAG检索异常，已降级跳过: {str(rag_err)[:100]}",
                    tool_name="rag_search", tool_args=user_message[:200],
                    tool_result="检索失败，已跳过",
                )
        else:
            logger.info("RAG未启用，跳过知识库检索")

        # 拼 RAG 上下文
        if rag_context:
            full_system_prompt = (
                f"{system_prompt}\n\n"
                f"=== 以下是从知识库检索到的参考资料，请基于这些内容回答用户问题 ===\n"
                f"{rag_context}\n"
                f"=== 参考资料结束 ===\n"
                f"注意：如果参考资料中没有相关信息，请如实告知用户。"
            )
        else:
            full_system_prompt = system_prompt

        # 4. 查历史对话
        history_chats = list_chats_by_agent(db, user_id, agent_id, limit=10)
        history = []
        for c in reversed(history_chats):
            history.append({"role": "user", "content": c.question})
            history.append({"role": "assistant", "content": c.answer})

        # 5. 创建 ToolExecutor + ReActEngine（和 run() 完全一致）
        executor = ToolExecutor(
            db=db,
            user_id=user_id,
            agent_id=agent_id,
            model_name=agent.model_name,
            temperature=agent.temperature / 100,
        )
        step_no_ref = {"value": 2 if agent.rag_enabled else 1}

        def write_step(step_info):
            """实时写轨迹到 AgentStep 表（和 run() 中完全一样）"""
            _record_react_step(db, run.id, step_no_ref, step_info, agent, user_message, rag_context)

        engine = executor.create_engine(
            max_iterations=5,
            step_callback=write_step,
        )

        # 6. 流式执行 ReAct（yield from 透传所有事件，并拿到最终返回值）
        stream_gen = engine.invoke_stream(
            system_prompt=full_system_prompt,
            user_message=user_message,
            history=history,
        )
        # Python生成器规则：用 try/except StopIteration 拿 return 的值
        try:
            while True:
                event = next(stream_gen)
                yield event
        except StopIteration as si:
            react_result = si.value

        answer = react_result.get("answer", "") or ""
        step_no = step_no_ref["value"] - 1 if step_no_ref["value"] > 1 else 1
        total_steps = step_no

        # 7. 更新 Run 状态 + 保存聊天记录（和 run() 一样）
        update_run_status(
            db=db, run=run, status="finished", final_answer=answer,
            total_steps=total_steps
        )
        create_chat(db, user_id, agent_id, user_message, answer)
        db.commit()

        # 8. 对话后：判断是否总结记忆（开关控制 + 失败降级）
        if agent.memory_enabled:
            try:
                if should_summarize(db, user_id, agent_id):
                    logger.info("开始总结长期记忆...")
                    summarize_and_save(db, user_id, agent_id, agent.model_name)
                    db.commit()
                    yield make_memory("summarized", "长期记忆总结完成")
                    logger.info("长期记忆总结完成")
            except Exception as mem_err:
                logger.warning(f"记忆总结失败（不影响对话结果）: {mem_err}")
                yield make_memory("error", f"记忆总结失败: {str(mem_err)[:100]}")
                db.rollback()

        # 9. 全部完成事件
        logger.info(
            f"Agent[stream] 运行完成: run_id={run.id}, steps={total_steps}, "
            f"answer长度={len(answer)}"
        )
        yield make_done(run.id, total_steps, len(answer))

    except Exception as e:
        # 任何未预期的异常：回滚 + 记录失败 + yield error
        db.rollback()
        logger.error(f"Agent[stream] 运行失败: run_id={run.id}, error={e}")
        try:
            from models.init_db import AgentRun
            run_record = db.query(AgentRun).filter(AgentRun.id == run.id).first()
            if run_record:
                run_record.status = "failed"
                run_record.error_msg = str(e)[:500]
                run_record.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        yield make_error(
            message="服务暂时异常，请稍后重试",
            detail=str(e)[:300]
        )
        return
# 新版：支持外部传入 history + conversation_id（供 chat_service 调用）旧的 run() 和 run_stream() 保留不动，保证向后兼容

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

        # RAG 降级
        rag_context = ""
        if agent.rag_enabled:
            step_no = 1
            try:
                logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
                results = await async_rag_search(db, user_id, agent_id, user_message, top_k=3)
                if results:
                    rag_context = "\n\n".join([
                        f"[知识片段{i+1}]\n{r['content']}"
                        for i, r in enumerate(results)
                    ])
                    logger.info(f"RAG检索完成: 命中{len(results)}条")
                    create_step(
                        db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                        thought=f"用户问题需要知识库辅助，检索到{len(results)}条相关片段",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result=_format_rag_audit(results, rag_context)
                    )
                else:
                    logger.info("RAG检索无结果，将直接使用LLM回答")
                    create_step(
                        db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                        thought="知识库中未检索到相关内容",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result="无匹配结果",
                    )
            except Exception as rag_err:
                logger.warning(f"RAG检索失败（降级跳过，不使用知识库）: {rag_err}")
                rag_context = ""
                create_step(
                    db=db, run_id=run.id, step_no=step_no, step_type="retrieval",
                    thought=f"RAG检索异常，已降级跳过: {str(rag_err)[:100]}",
                    tool_name="rag_search", tool_args=user_message[:200],
                    tool_result="检索失败，已跳过",
                )
        else:
            logger.info("RAG未启用，跳过知识库检索")

        # 拼接 RAG 上下文
        if rag_context:
            full_system_prompt = (
                f"{system_prompt}\n\n"
                f"=== 以下是从知识库检索到的参考资料，请基于这些内容回答用户问题 ===\n"
                f"{rag_context}\n"
                f"=== 参考资料结束 ===\n"
                f"注意：如果参考资料中没有相关信息，请如实告知用户。"
            )
        else:
            full_system_prompt = system_prompt

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
                run_record.finished_at = datetime.utcnow()
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

        # RAG 降级
        rag_context = ""
        if agent.rag_enabled:
            try:
                logger.info(f"RAG已启用，开始检索: query='{user_message[:30]}...'")
                results = rag_search(db, user_id, agent_id, user_message, top_k=3)
                if results:
                    rag_context = "\n\n".join([
                        f"[知识片段{i+1}]\n{r['content']}"
                        for i, r in enumerate(results)
                    ])
                    logger.info(f"RAG检索完成: 命中{len(results)}条")
                    yield make_retrieval(hit_count=len(results), content_preview=rag_context)
                    create_step(
                        db=db, run_id=run.id, step_no=1, step_type="retrieval",
                        thought=f"用户问题需要知识库辅助，检索到{len(results)}条相关片段",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result=_format_rag_audit(results, rag_context)
                    )
                else:
                    logger.info("RAG检索无结果")
                    yield make_retrieval(hit_count=0, content_preview="知识库无匹配内容")
                    create_step(
                        db=db, run_id=run.id, step_no=1, step_type="retrieval",
                        thought="知识库中未检索到相关内容",
                        tool_name="rag_search", tool_args=user_message[:200],
                        tool_result="无匹配结果",
                    )
            except Exception as rag_err:
                logger.warning(f"RAG检索失败（降级跳过）: {rag_err}")
                yield make_retrieval(hit_count=0, content_preview=f"检索异常已跳过: {str(rag_err)[:100]}")
                create_step(
                    db=db, run_id=run.id, step_no=1, step_type="retrieval",
                    thought=f"RAG检索异常，已降级跳过: {str(rag_err)[:100]}",
                    tool_name="rag_search", tool_args=user_message[:200],
                    tool_result="检索失败，已跳过",
                )
        else:
            logger.info("RAG未启用，跳过知识库检索")

        # 拼接 RAG 上下文
        if rag_context:
            full_system_prompt = (
                f"{system_prompt}\n\n"
                f"=== 以下是从知识库检索到的参考资料，请基于这些内容回答用户问题 ===\n"
                f"{rag_context}\n"
                f"=== 参考资料结束 ===\n"
                f"注意：如果参考资料中没有相关信息，请如实告知用户。"
            )
        else:
            full_system_prompt = system_prompt

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
                run_record.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        yield make_error(
            message="服务暂时异常，请稍后重试",
            detail=str(e)[:300]
        )
        return
