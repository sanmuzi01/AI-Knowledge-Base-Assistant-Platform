"""
Memory 记忆服务：长期记忆管理
核心功能：
  1. load_memory()   - 加载已有的长期记忆（给Runtime拼prompt用）
  2. should_summarize() - 判断是否该总结新对话了（每N轮总结一次）
  3. summarize_and_save() - 调LLM把旧对话总结成摘要，覆盖旧记忆
  - 不总结最近5轮（作为短期记忆保留原文）
  - 超过5轮的旧对话 → LLM压缩成一段摘要
  - 每累计5轮新对话就重新总结一次，避免记忆过期
  - 长期记忆拼在system_prompt里，LLM随时能看到
"""
from typing import Dict, List, Optional
from utils.logger_handler import get_logger
from models.agent_run_dao import count_finished_runs_by_agent, list_finished_runs_by_agent
from service.access_control import get_owned_agent, get_owned_memory
from models.memory_dao import (
    create_memory,
    delete_memories_by_user_agent,
    delete_memory,
    get_latest_summary,
    list_memories_by_agent,
    update_memory,
)
logger = get_logger("memory_service")
# 每多少轮对话总结一次
SUMMARY_EVERY_N_ROUNDS = 5
# 短期记忆保留多少轮原文
SHORT_TERM_ROUNDS = 5

VALID_MEMORY_TYPES = {"summary", "fact", "preference", "note"}

def memory_to_dict(memory) -> Dict:
    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "agent_id": memory.agent_id,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "chat_count": memory.chat_count,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
    }

def ensure_agent_owner(db, user_id: int, agent_id: int):
    return get_owned_agent(db, user_id, agent_id)

def list_agent_memories(db, user_id: int, agent_id: int) -> Optional[List[Dict]]:
    if not ensure_agent_owner(db, user_id, agent_id):
        return None
    return [memory_to_dict(memory) for memory in list_memories_by_agent(db, user_id, agent_id)]

def add_memory(db, user_id: int, agent_id: int, memory_type: str, content: str) -> Optional[Dict]:
    if not ensure_agent_owner(db, user_id, agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type)
    memory = create_memory(
        db=db,
        user_id=user_id,
        agent_id=agent_id,
        memory_type=normalized_type,
        content=content.strip(),
        chat_count=0,
    )
    db.commit()
    return memory_to_dict(memory)

def edit_memory(db, user_id: int, memory_id: int, memory_type: str = None, content: str = None) -> Optional[Dict]:
    memory = get_owned_memory(db, user_id, memory_id)
    if not memory or not ensure_agent_owner(db, user_id, memory.agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type) if memory_type is not None else None
    next_content = content.strip() if content is not None else None
    updated = update_memory(db, memory, memory_type=normalized_type, content=next_content)
    db.commit()
    return memory_to_dict(updated)

def remove_memory(db, user_id: int, memory_id: int) -> bool:
    memory = get_owned_memory(db, user_id, memory_id)
    if not memory or not ensure_agent_owner(db, user_id, memory.agent_id):
        return False
    delete_memory(db, memory)
    db.commit()
    return True

def clear_agent_memories(db, user_id: int, agent_id: int) -> Optional[int]:
    if not ensure_agent_owner(db, user_id, agent_id):
        return None
    count = delete_memories_by_user_agent(db, user_id, agent_id)
    db.commit()
    return count

def _normalize_memory_type(memory_type: str) -> str:
    value = (memory_type or "").strip().lower()
    if value not in VALID_MEMORY_TYPES:
        raise ValueError("记忆类型不支持")
    return value

_MEMORY_LABELS = {
    "summary": "对话摘要",
    "fact": "关键事实",
    "preference": "用户偏好",
    "note": "备注",
}


def render_memory_text(memories) -> str:
    """把记忆列表拼成注入 system_prompt 的文本（同步 / 异步共用，保证输出一致）。

    memories: 已按 created_at desc 排序的 Memory 列表；此函数负责过滤空内容 + 拼装。
    """
    memories = [m for m in memories if m.content and m.content.strip()]
    if not memories:
        return ""
    lines = [
        f"- [{_MEMORY_LABELS.get(m.memory_type, m.memory_type)}] {m.content.strip()}"
        for m in memories
    ]
    memory_text = (
        "\n=== 以下是你和用户的长期对话记忆，请结合这些内容理解用户 ==="
        "\n" + "\n".join(lines) + "\n"
        "=== 长期记忆结束 ===\n"
    )
    logger.debug(f"加载长期记忆: {len(memories)} 条, {len(memory_text)} 字")
    return memory_text


def summary_due(total_count: int, last_summary_count: int) -> bool:
    """当前总对话轮数 - 上次总结时的轮数 >= SUMMARY_EVERY_N_ROUNDS（同步 / 异步共用）。"""
    diff = total_count - last_summary_count
    result = diff >= SUMMARY_EVERY_N_ROUNDS
    if result:
        logger.info(
            f"触发记忆总结: 总对话{total_count}轮, "
            f"上次总结于{last_summary_count}轮, 差值={diff} >= {SUMMARY_EVERY_N_ROUNDS}"
        )
    return result


def load_memory(db,user_id:int,agent_id:int)->str:
    """加载长期记忆，拼成文本（给Runtime拼到system_prompt里）
    如果没有记忆，返回空字符串（Runtime不会额外拼接东西）"""
    memories = list_memories_by_agent(db, user_id, agent_id)
    return render_memory_text(memories)

def should_summarize(db,user_id:int,agent_id:int)->bool:
    """判断是否该总结新对话了
          当前总对话轮数 - 上次总结时的轮数 >= SUMMARY_EVERY_N_ROUNDS（5）
        """
    # 以 AgentRun 为准，兼容旧聊天入口和新版会话入口。
    total_count = count_finished_runs_by_agent(db, user_id, agent_id)
    summary = get_latest_summary(db,user_id,agent_id)
    last_summary_count = summary.chat_count if summary else 0
    return summary_due(total_count, last_summary_count)

def summarize_and_save(
        db,user_id:int,agent_id:int,llm_model_name:str = "glm-4"
)->Optional[str]:
    """总结旧对话 → 生成记忆摘要 → 覆盖旧摘要存DB
          1. 查所有对话（最多1000轮，足够用了）
          2. 短期记忆（最近5轮）不总结，直接跳过
          3. 超过5轮的旧对话 + 上次的旧摘要（如果有的话）拼成文本
          4. 调LLM生成一个新的摘要
          5. 删除旧摘要，存新摘要
          避免新总结把久远的信息丢了。
          比如用户在第1轮说"我叫张三"，到第100轮总结时，如果只看第6-100轮，
          就会丢了"张三"这个信息。带上旧摘要就能保留下来。"""
    from service.llm.llm_service import chat as llm_chat

    # 1.查所有成功运行记录（取最近1000轮，倒序）
    runs = list_finished_runs_by_agent(db, user_id, agent_id, limit=1000)
    if len(runs) <= SHORT_TERM_ROUNDS:
        logger.info(f"对话只有{len(runs)}轮，少于短期记忆{SHORT_TERM_ROUNDS}轮，不总结")
        return None
    # 2.分离：短期（最近5轮不总结）长期（旧对话，要总结）chats是倒序的（[最新, ..., 最旧]）
    old_runs = runs[SHORT_TERM_ROUNDS:]# 剩下的旧对话
    # 3.取上次的旧摘要（如果有）
    old_summary_obj = get_latest_summary(db,user_id,agent_id)
    old_summary_text = old_summary_obj.content if old_summary_obj else ""
    # 4.组装"待总结文本"：旧对话原文 + 旧摘要
    chat_text = _format_runs_for_summary(old_runs)
    # 5.构造总结prompt
    summarize_prompt = _build_summary_prompt(
        old_summary = old_summary_text,new_chats_text = chat_text)
    # 6.调LLM总结（system_prompt=None，让LLM专注于总结任务）
    try:
        new_summary = llm_chat(
            db=db,user_id=user_id,model_name=llm_model_name,
            system_prompt=(
                "你是一个专业的对话记忆总结助手。"
                "你的任务是：从对话中提取关键信息并压缩成简洁的摘要，"
                "不要遗漏用户的关键事实（如姓名、职业、偏好、项目背景等）。"
                "直接输出摘要，不要用任何解释性语言。"
            ),
            history = [],  # 不需要上下文
            user_message = summarize_prompt,
            temperature = 0.1,  # 温度低一点，更稳定
        )
    except Exception as e:
        logger.warning(f"记忆总结失败: {e}，将在下次对话时重试")
        return None

    if not new_summary or not new_summary.strip():
        logger.warning("记忆总结返回空内容，跳过保存")
        return None
    # 7.删旧摘要（如果有）
    if old_summary_obj:
        delete_memory(db, old_summary_obj)
        logger.info(f"删除旧摘要: id={old_summary_obj.id}")
    #8,存新摘要
    total_chats = len(runs)
    create_memory(
        db,user_id=user_id,agent_id=agent_id,memory_type="summary",
        content=new_summary.strip(),chat_count=total_chats,
    )
    logger.info(
        f"记忆总结完成: {len(old_runs)}轮旧对话 → "
        f"{len(new_summary.strip())}字摘要, 当前总对话{total_chats}轮"
    )
    try:
        from service.user_profile_service import infer_user_profile_from_summary

        inferred = infer_user_profile_from_summary(
            db=db,
            user_id=user_id,
            agent_id=agent_id,
            memory_summary=new_summary,
            llm_model_name=llm_model_name,
        )
        if inferred:
            logger.info(f"用户画像自动提炼完成: {len(inferred)}字")
    except Exception as e:
        logger.warning(f"用户画像自动提炼失败（不影响记忆总结）: {e}")
    return new_summary


def _format_runs_for_summary(runs) -> str:
    """把运行记录格式化成“用户/助手”对话文本。"""
    sorted_runs = list(reversed(runs))
    lines = []
    for i, run in enumerate(sorted_runs):
        lines.append(f"轮次{i+1} 用户: {run.user_message}")
        lines.append(f"轮次{i+1} 助手: {run.final_answer}")
    return "\n".join(lines)


def _format_chats_for_summary(chats)->str:
    """把旧对话列表格式化成"用户：xxx\n助手：xxx\n..."的文本
        chats是倒序的，要反转为正序再格式化。"""
    sorted_chats = list(reversed(chats))
    lines = []
    for i,c in enumerate(sorted_chats):
        lines.append(f"轮次{i+1} 用户: {c.question}")
        lines.append(f"轮次{i+1} 助手: {c.answer}")
    return "\n".join(lines)
def _build_summary_prompt(old_summary: str, new_chats_text: str) -> str:
    """构造总结prompt
       如果有旧摘要，要求新摘要要"基于旧摘要+新对话"合并
       明确告诉LLM不要丢失旧摘要中的关键事实"""
    if old_summary:
        return (
            "基于以下【已有记忆摘要】和【新增对话】，生成一段新的完整记忆摘要。\n"
            "要求：\n"
            "1. 完整保留已有记忆摘要中的所有关键信息（用户姓名、背景、偏好等）\n"
            "2. 把新增对话中的新信息合并进去\n"
            "3. 总字数控制在300字以内，简洁明了\n"
            "4. 直接输出摘要，不要加任何标题或解释\n\n"
            f"【已有记忆摘要】\n{old_summary}\n\n"
            f"【新增对话】\n{new_chats_text}\n"
        )
    else:
        return (
            "根据以下对话历史，生成一段简洁的记忆摘要。\n"
            "要求：\n"
            "1. 提取用户的关键信息（姓名、背景、兴趣、偏好、项目等）\n"
            "2. 总结对话的核心主题\n"
            "3. 总字数控制在300字以内\n"
            "4. 直接输出摘要，不要加任何标题或解释\n\n"
            f"【对话历史】\n{new_chats_text}\n"
        )
