"""
聊天 Service 业务层（全量 AsyncSession）
职责：
  1. 归属校验（Agent 必须属于当前用户，Conversation 必须属于当前用户）
  2. 会话管理（conversation_id 为空时自动新建）
  3. 消息保存（发前存 user，发后存 assistant）
  4. 历史加载（把 conversation 历史传给 ReAct 引擎）
  5. 调用 Agent Runtime（非流式 run_with_history_async / 流式 run_stream_with_history_async）
  6. 首条消息自动生成会话标题
"""
from typing import Dict, Any, Optional
from service.access_control import get_owned_agent_async, get_owned_conversation_async
from service.runtime import agent_runtime
from utils.logger_handler import get_logger
import service.conversation_async_service as conv_async
import models.conversation_async_dao as conv_async_dao
logger = get_logger("chat_service")
# 同步对话（非流式）：阶段 2 起整条走 AsyncSession（get_async_db）。
# 兼容不变：conversation_id=None 自动新建会话并在返回体里带回。
async def chat_with_agent(db, user, agent_id: int, user_message: str,conversation_id: Optional[int] = None,) -> Dict[str, Any]:
    """用户与智能体对话：验证归属 → 交给Runtime执行 → 返回结果"""
    # 1. 验证智能体归属权（这层只管权限，不管怎么推理）
    agent = await get_owned_agent_async(db, user.id, agent_id)
    if not agent:
        logger.warning(f"用户 {user.id} 尝试访问不属于自己的智能体 {agent_id}")
        raise ValueError("智能体不存在或不属于您")
    # 2. 会话管理：conversation_id 空 → 新建；非空 → 校验归属
    if conversation_id is None:
        conv = await conv_async_dao.create_conversation_async(db, user_id=user.id, agent_id=agent_id)
        conversation_id = conv.id
        logger.info(f"自动新建会话: id={conversation_id}, agent_id={agent_id}")
    else:
        conv = await get_owned_conversation_async(db, user.id, conversation_id, agent_id=agent_id)
        if not conv:
            logger.warning(f"会话归属校验失败: conv={conversation_id}, user={user.id}, agent={agent_id}")
            raise ValueError("会话不存在或不属于您")

    # 3. 保存用户消息 + 自动生成标题（run_with_history_async 会尽早 commit，用户消息因此稳定落库）
    await conv_async.save_message_async(db, conversation_id, "user", user_message)
    await conv_async.maybe_update_title_by_first_message_async(db, conversation_id, user_message)
    await db.flush()

    # 4. 加载历史（给 LLM 上下文）
    history = await conv_async.load_history_for_llm_async(db, conversation_id, limit=20)
    # 去掉刚存的这条 user 消息（ReAct 会通过 user_message 再传一次，避免重复）
    if history and history[-1]["role"] == "user" and history[-1]["content"] == user_message:
        history = history[:-1]

    # 5. 调用 Agent Runtime
    try:
        result = await agent_runtime.run_with_history_async(
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
    await conv_async.save_message_async(db, conversation_id, "assistant", answer)
    await db.flush()
    await db.commit()
    # 7. 返回时带 conversation_id，前端保存以便下一轮消息复用
    result["conversation_id"] = conversation_id
    return result
async def chat_with_agent_stream_async(db, user, agent_id: int, user_message: str,
                                       conversation_id: Optional[int] = None):
    """流式对话（SSE，AsyncSession 版）。阶段 3 起 `POST /chat/{id}/stream` 走这条。

    事件透传：转发 runtime 的每个事件，从 `answer` 事件里抠出最终回答，流结束后存 AI 消息 + commit，
    再补一个带 conversation_id 的 done 事件（run_id / steps 置空——前端用 runtime 那个 done）。
    """
    from service.runtime.sse_events import make_error, make_done

    agent = await get_owned_agent_async(db, user.id, agent_id)
    if not agent:
        logger.warning(f"用户 {user.id} 尝试访问不属于自己的智能体 {agent_id}")
        yield make_error("智能体不存在或不属于您")
        return

    if conversation_id is None:
        conv = await conv_async_dao.create_conversation_async(db, user_id=user.id, agent_id=agent_id)
        conversation_id = conv.id
        logger.info(f"自动新建会话: id={conversation_id}, agent_id={agent_id}")
    else:
        conv = await get_owned_conversation_async(db, user.id, conversation_id, agent_id=agent_id)
        if not conv:
            logger.warning(f"会话归属校验失败: conv={conversation_id}, user={user.id}, agent={agent_id}")
            yield make_error("会话不存在或不属于您")
            return

    await conv_async.save_message_async(db, conversation_id, "user", user_message)
    await conv_async.maybe_update_title_by_first_message_async(db, conversation_id, user_message)
    await db.flush()

    history = await conv_async.load_history_for_llm_async(db, conversation_id, limit=20)
    if history and history[-1]["role"] == "user" and history[-1]["content"] == user_message:
        history = history[:-1]

    final_answer = ""
    try:
        async for event in agent_runtime.run_stream_with_history_async(
            db=db, user_id=user.id, agent_id=agent_id,
            user_message=user_message, history=history, conversation_id=conversation_id,
        ):
            yield event
            if isinstance(event, str) and event.startswith("event: answer"):
                try:
                    import json
                    data_line = event.split("\n", 1)[1]
                    data_str = data_line[data_line.index(":") + 1:].strip()
                    final_answer = json.loads(data_str).get("content", "") or ""
                except Exception as parse_err:  # noqa: BLE001
                    logger.debug(f"解析 answer 事件失败，走兜底: {parse_err}")
    except ValueError as e:
        yield make_error(str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"流式对话异常: {e}")
        yield make_error(message="服务暂时异常，请稍后重试", detail=str(e)[:300])
        return

    if final_answer:
        await conv_async.save_message_async(db, conversation_id, "assistant", final_answer)
        await db.flush()
    await db.commit()

    ans_tokens = max(1, len(final_answer) // 2) if final_answer else 0
    yield make_done(
        run_id=None,
        steps=0,
        answer_length=len(final_answer) if final_answer else 0,
        conversation_id=conversation_id,
        tokens=ans_tokens,
    )
