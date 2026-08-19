from typing import List,Optional
from models.init_db import AgentStep,AgentRun
from datetime import datetime
# ========== AgentRun 相关 ==========
def create_run(
        db,user_id:int,agent_id:int,
        user_message:str,chat_id:int=None,
        conversation_id: int = None,  # ← 新增
):
    """创建一次Agent运行记录（初始状态为running）"""
    run = AgentRun(
        user_id = user_id,
        agent_id = agent_id,
        user_message=user_message,
        chat_id=chat_id,
        conversation_id=conversation_id,  # ← 新增
        status = "running"
    )
    db.add(run)
    db.flush()
    return run

def update_run_status(
        db,run:AgentRun,status:str,final_answer:str=None,
        total_steps:int=None,total_tokens:int=None,
        error_msg:str=None)->AgentRun:
    """更新运行状态（结束时调用）"""
    run.status = status
    if final_answer is not None:
        run.final_answer = final_answer
    if total_steps is not None:
        run.total_steps = total_steps
    if total_tokens is not None:
        run.total_tokens = total_tokens
    if error_msg is not None:
        run.error_msg = error_msg
    run.finished_at = datetime.utcnow()
    db.flush()
    return run

def get_run_by_id(db,run_id:int)->Optional[AgentRun]:
    """根据ID查询单次运行"""
    return db.query(AgentRun).filter(AgentRun.id == run_id).first()

def list_runs_by_agent(
        db, agent_id: int, limit: int = 50,
        conversation_id: Optional[int] = None,
) -> List[AgentRun]:
    """查询某 Agent 的历史运行（按开始时间倒序）
    conversation_id 有值时只返回该会话下的 run（会话隔离）
    """
    q = db.query(AgentRun).filter(AgentRun.agent_id == agent_id)
    if conversation_id is not None:
        q = q.filter(AgentRun.conversation_id == conversation_id)
    return q.order_by(AgentRun.started_at.desc()).limit(limit).all()
def list_runs_by_user(db,user_id:int,limit:int=50)-> List[AgentRun]:
    """查询某用户的所有运行（跨Agent）"""
    return (
        db.query(AgentRun).filter(AgentRun.user_id==user_id)
        .order_by(AgentRun.started_at.desc()).limit(limit).all()
    )
# ========== AgentStep 相关 ==========

def create_step(
        db,run_id:int,step_no:int,step_type:str,
        thought:str= None,tool_name:str=None,tool_args:str=None,tool_result:str=None,
        tokens:int=0,) -> AgentStep:
    """记录运行中的一个步骤"""
    step=AgentStep(run_id = run_id,step_no=step_no,step_type = step_type,
                   thought=thought,tool_name=tool_name,tool_args=tool_args,
                   tool_result = tool_result,tokens=tokens)
    db.add(step)
    db.flush()
    return step

def list_steps_by_run(db,run_id:int)->List[AgentStep]:
    """查询某次运行的所有步骤（按步号正序）"""
    return (
        db.query(AgentStep).filter(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_no.asc()).all()
    )
