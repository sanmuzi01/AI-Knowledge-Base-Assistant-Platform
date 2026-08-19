"""
聊天 Service 业务层
职责：
  1. 归属校验（Agent 必须属于当前用户，Conversation 必须属于当前用户）
  2. 会话管理（conversation_id 为空时自动新建）
  3. 消息保存（发前存 user，发后存 assistant）
  4. 历史加载（把 conversation 历史传给 ReAct 引擎）
  5. 调用 Agent Runtime（同步/流式两种）
  6. 首条消息自动生成会话标题
"""
from typing import Dict, Any,Generator, Optional
from service.access_control import get_owned_agent, get_owned_conversation
from service.runtime import agent_runtime
from utils.logger_handler import get_logger
import service.conversation_service as conv_service
import models.conversation_dao as conv_dao
logger = get_logger("chat_service")
# 同步对话（保留原接口兼容：conversation_id=None 时向后兼容旧调用方）
def chat_with_agent(db, user, agent_id: int, user_message: str,conversation_id: Optional[int] = None,) -> Dict[str, Any]:
    """用户与智能体对话：验证归属 → 交给Runtime执行 → 返回结果"""
    # 1. 验证智能体归属权（这层只管权限，不管怎么推理）
    agent = get_owned_agent(db, user.id, agent_id)
    if not agent:
        logger.warning(f"用户 {user.id} 尝试访问不属于自己的智能体 {agent_id}")
        raise ValueError("智能体不存在或不属于您")
    # 2. 会话管理：conversation_id 空 → 新建；非空 → 校验归属
    if conversation_id is None:
        conv = conv_dao.create_conversation(db, user_id=user.id, agent_id=agent_id)
        conversation_id = conv.id
        logger.info(f"自动新建会话: id={conversation_id}, agent_id={agent_id}")
    else:
        conv = get_owned_conversation(db, user.id, conversation_id, agent_id=agent_id)
        if not conv:
            logger.warning(f"会话归属校验失败: conv={conversation_id}, user={user.id}, agent={agent_id}")
            raise ValueError("会话不存在或不属于您")

    # 3. 保存用户消息 + 自动生成标题
    conv_service.save_message(db, conversation_id, "user", user_message)
    conv_service.maybe_update_title_by_first_message(db, conversation_id, user_message)
    db.flush()

    # 4. 加载历史（给 LLM 上下文）
    history = conv_service.load_history_for_llm(db, conversation_id, limit=20)
    # 去掉刚存的这条 user 消息（ReAct 会通过 user_message 再传一次，避免重复）
    if history and history[-1]["role"] == "user" and history[-1]["content"] == user_message:
        history = history[:-1]

    # 5. 调用 Agent Runtime
    try:
        result = agent_runtime.run_with_history(
            db=db,
            user_id=user.id,
            agent_id=agent_id,
            user_message=user_message,
            history=history,
            conversation_id=conversation_id,
        )
    except ValueError as e:
        return {"message": str(e), "conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"同步对话失败: {e}")
        return {"message": "服务暂时异常，请稍后重试", "conversation_id": conversation_id}

    # 6. 保存 AI 消息
    answer = result.get("answer", "") or ""
    conv_service.save_message(db, conversation_id, "assistant", answer)
    db.flush()
    # 7. 返回时带 conversation_id，前端保存以便下一轮消息复用
    result["conversation_id"] = conversation_id
    return result
# 流式对话（SSE）：同样支持 conversation_id
def chat_with_agent_stream(db, user, agent_id: int, user_message: str, conversation_id: Optional[int] = None) -> Generator[str, None, None]:
    """流式对话（SSE 生成器）
    conversation_id: 可选。None=自动新建会话"""
    from service.runtime.sse_events import make_error
    # 1.验证智能体归属权
    agent = get_owned_agent(db, user.id, agent_id)
    if not agent:
        logger.warning(f"用户 {user.id} 尝试访问不属于自己的智能体 {agent_id}")
        yield make_error("智能体不存在或不属于您")
        return
    # 2. 会话管理：conversation_id 空 → 新建；非空 → 校验归属
    if conversation_id is None:
        conv = conv_dao.create_conversation(db, user_id=user.id, agent_id=agent_id)
        conversation_id = conv.id
        logger.info(f"自动新建会话: id={conversation_id}, agent_id={agent_id}")
    else:
        conv = get_owned_conversation(db, user.id, conversation_id, agent_id=agent_id)
        if not conv:
            logger.warning(f"会话归属校验失败: conv={conversation_id}, user={user.id}, agent={agent_id}")
            yield make_error("会话不存在或不属于您")
            return
    # 3. 保存用户消息 + 自动生成标题（首条消息时）
    user_msg = conv_service.save_message(db, conversation_id, "user", user_message)
    conv_service.maybe_update_title_by_first_message(db, conversation_id, user_message)
    db.flush()
    # 4. 加载历史（给 LLM 上下文）
    history = conv_service.load_history_for_llm(db, conversation_id, limit=20)
    # 去掉刚存的 user 消息，避免 ReAct 重复处理
    if history and history[-1]["role"] == "user" and history[-1]["content"] == user_message:
        history = history[:-1]
    # 5. 调用 Agent Runtime 流式执行，透传事件 + 捕获最终回答
    final_answer = ""
    try:
        stream_gen = agent_runtime.run_stream_with_history(
            db=db,
            user_id=user.id,
            agent_id=agent_id,
            user_message=user_message,
            history=history,
            conversation_id=conversation_id,
        )
        # Python 生成器：用 try/except StopIteration 拿 return 的值
        try:
            while True:
                event = next(stream_gen)
                yield event
                # 解析 answer 事件拿到最终回答
                if isinstance(event, str) and event.startswith("event: answer"):
                    try:
                        import json
                        data_line = event.split("\n", 1)[1]  # "data: {...}"
                        data_str = data_line[data_line.index(":") + 1:].strip()
                        data_obj = json.loads(data_str)
                        final_answer = data_obj.get("content", "") or ""
                    except Exception:
                        pass
        except StopIteration as si:
            runtime_result = si.value
            if isinstance(runtime_result, dict) and not final_answer:
                final_answer = runtime_result.get("answer", "") or ""
    except ValueError as e:
        yield make_error(str(e))
    except Exception as e:
        logger.error(f"流式对话异常: {e}")
        yield make_error(
            message="服务暂时异常，请稍后重试",
            detail=str(e)[:300]
        )
        return

    # 6. 保存 AI 消息 + 提交事务（流式必须在生成器内 commit）
    if final_answer:
        conv_service.save_message(db, conversation_id, "assistant", final_answer)
        db.flush()
    db.commit()  # 必须 commit（包含首条消息自动生成的会话标题也要落盘）

    # 7. 发 done 事件（带 conversation_id → 前端刷新左侧会话栏）
    from service.runtime.sse_events import make_done
    ans_tokens = max(1, len(final_answer) // 2) if final_answer else 0
    total_steps = (
        runtime_result.get("total_steps", 0)
        if isinstance(runtime_result, dict) else 0
    )
    run_id = runtime_result.get("run_id") if isinstance(runtime_result, dict) else None
    yield make_done(
        run_id=run_id,
        steps=total_steps,
        answer_length=len(final_answer) if final_answer else 0,
        conversation_id=conversation_id,
        tokens=ans_tokens,
    )
