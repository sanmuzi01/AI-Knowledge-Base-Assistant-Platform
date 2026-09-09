from utils.timeutil import utcnow
from typing import List
from typing import Generator
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Table, Index, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, relationship
from dotenv import load_dotenv
import os


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，格式错误时使用默认值，避免配置错误导致应用直接崩溃。"""

    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = True) -> bool:
    """读取布尔环境变量，支持 1/true/yes/on 和 0/false/no/off。"""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# 数据库连接
load_dotenv()
DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")
DB_HOST=os.getenv("DB_HOST")
DB_PORT=os.getenv("DB_PORT")
DB_NAME=os.getenv("DB_NAME")
missing_db_config = [
    name for name, value in {
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_HOST": DB_HOST,
        "DB_PORT": DB_PORT,
        "DB_NAME": DB_NAME,
    }.items()
    if not value
]
if missing_db_config:
    raise RuntimeError(f"缺少数据库环境变量: {', '.join(missing_db_config)}")
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DB_POOL_SIZE = _env_int("DB_POOL_SIZE", 10)
DB_MAX_OVERFLOW = _env_int("DB_MAX_OVERFLOW", 20)
DB_POOL_TIMEOUT = _env_int("DB_POOL_TIMEOUT", 30)
DB_POOL_RECYCLE = _env_int("DB_POOL_RECYCLE", 1800)
DB_POOL_PRE_PING = _env_bool("DB_POOL_PRE_PING", True)

# 数据库连接池：
# pool_pre_ping 会在取连接前探测连接是否还活着，避免 MySQL 空闲断开后请求直接报错。
# pool_recycle 主动回收旧连接，应小于 MySQL wait_timeout，适合长时间运行的生产服务。
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    pool_pre_ping=DB_POOL_PRE_PING,
    pool_use_lifo=True,
    connect_args={"charset": "utf8mb4"},
)

# ORM基类
Base = declarative_base()
# 用户角色关联表
association_table = Table(
    "user_role",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id"),primary_key=True),
    Column("role_id", Integer, ForeignKey("role.id"),primary_key=True)
)
# 用户表
class User(Base):
    __tablename__ = "user"
    id = Column(Integer,primary_key=True,autoincrement=True)
    name = Column(String(255),nullable=False,unique=True)
    phone = Column(String(20),nullable=True,unique=True)
    password = Column(String(255),nullable=False)
    age = Column(Integer)
    is_disabled = Column(Integer, default=0)
    last_login_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    selected_agent_id = Column(Integer,ForeignKey("agent.id", name="fk_user_selected_agent"),nullable=True)    #关联关系
    roles:Mapped[List["Role"]]=relationship(secondary=association_table,lazy=False,back_populates="users")
    #1对1的关系
    #role = relationship("Role",lazy=False,back_populates="user")


class UserProfile(Base):
    """用户画像：保存用户希望 AI 长期遵循的身份、偏好和沟通方式。"""
    __tablename__ = "user_profile"
    __table_args__ = (
        Index("idx_user_profile_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_user_profile_user"), nullable=False, unique=True)
    occupation = Column(String(100), nullable=True)              # 职业/身份
    skills = Column(Text, nullable=True)                         # 技能背景
    preferences = Column(Text, nullable=True)                    # 长期偏好
    communication_style = Column(String(50), default="balanced") # 回答风格
    persona = Column(String(50), default="professional")         # 助手人格
    extra_info = Column(Text, nullable=True)                     # 其他补充信息
    auto_summary = Column(Text, nullable=True)                   # AI 自动提炼的用户画像
    last_inferred_at = Column(DateTime, nullable=True)           # 最近一次自动画像更新时间
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class UserWorkspace(Base):
    """用户工作台配置：保存每个用户自己的模块、小窗口和布局。"""
    __tablename__ = "user_workspace"
    __table_args__ = (
        Index("idx_user_workspace_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_user_workspace_user"), nullable=False, unique=True)
    modules_json = Column(Text, nullable=False)
    widgets_json = Column(Text, nullable=False)
    layout_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


# 智能体表
class Agent(Base):
    __tablename__ = "agent"
    __table_args__ = (
        Index("idx_agent_user_id_id", "user_id", "id"),
    )
    id = Column(Integer,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id", name="fk_agent_user"),nullable=False)
    name = Column(String(255),nullable=False)
    # Prompt文件路径
    prompt_file = Column( String(255),nullable=True)
    model_name = Column(String(100), default="glm-4")             # 用的大模型
    rag_enabled = Column(Integer, default=0)                       # 是否启用RAG（0=否，1=是），总开关
    memory_enabled = Column(Integer, default=1)                    # 是否启用长期记忆（0=否，1=是）
    temperature = Column(Integer, default=70)                      # 温度参数（0-100，控制创造性）
    # ---- 知识库空间检索行为（阶段1 加列；阶段3 接线）----
    kb_top_k = Column(Integer, nullable=False, default=5)
    kb_rerank_enabled = Column(Integer, nullable=False, default=0)
    kb_force_citation = Column(Integer, nullable=False, default=1)     # 回答强制带来源
    kb_refuse_when_empty = Column(Integer, nullable=False, default=1)  # 无命中时拒答
    skills: Mapped[List["Skill"]] = relationship(
        secondary="agent_skill", lazy=False, back_populates="agents"
    )
# 角色表
class Role(Base):
    __tablename__ = "role"
    id = Column(Integer,primary_key=True,autoincrement=True)
    role_name = Column(String(255),nullable=False,unique=True)
    description = Column(String(255))
    #关联关系
    users:Mapped[List["User"]]=relationship(secondary=association_table,lazy=False,back_populates="roles")
    #1对1的关系
    #user = relationship("User",lazy=False,back_populates="role")
#llm的apikey
class LLMConfig(Base):
    __tablename__ = "llm_config"
    __table_args__ = (
        Index("idx_llm_config_user_model", "user_id", "model_name"),
        Index("idx_llm_config_user_active", "user_id", "is_active"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    model_name = Column(String(100), nullable=False)  # "glm-4" / "gpt-4o" / "deepseek-chat"
    api_key = Column(String(500), nullable=False)      # 用户填写的 API Key（加密存储）
    api_url = Column(String(500))                      # 可选，自定义端点
    is_active = Column(Integer, default=1)             # 0=停用, 1=启用
# 聊天记录表
class Chat(Base):
    __tablename__ = "chat"
    __table_args__ = (
        Index("idx_chat_user_agent_time", "user_id", "agent_id", "create_time"),
    )
    id = Column(Integer,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id"))
    agent_id = Column(Integer,ForeignKey("agent.id"))
    question = Column(Text,nullable=False)
    answer = Column(Text,nullable=False)
    create_time = Column(DateTime,nullable=False)
# 工具表
class Tool(Base):
    __tablename__ = "tool"
    id = Column(Integer,primary_key=True,autoincrement=True)
    agent_id = Column(Integer,ForeignKey("agent.id"))
    tool_name = Column(String(255),nullable=False)
    tool_type = Column(String(255),nullable=False)
# 知识库文档表（上传的原始文档元数据）
class Knowledge(Base):
    __tablename__ = "knowledge"
    __table_args__ = (
        Index("idx_knowledge_user_created", "user_id", "created_at"),
        Index("idx_knowledge_agent_created", "agent_id", "created_at"),
        Index("idx_knowledge_agent_enabled_status", "agent_id", "is_enabled", "status"),
    )
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id",name="fk_knowledge_user"),nullable=False)
    # 知识库空间升级后：文档归属 space_id；agent_id 改为可空（存量文档保留旧值，空间上传的文档为 NULL）
    agent_id = Column(Integer,ForeignKey("agent.id",name="fk_knowledge_agent"),nullable=True)
    file_name = Column(String(255),nullable=False) # 原始文件名
    file_path = Column(String(500),nullable=False) #磁盘存储路径
    file_type = Column(String(50),nullable=False) # pdf/docx/txt/md
    file_size = Column(Integer,default=0) # 字节数
    chunk_count =Column(Integer,default=0) # 切块数（解析后回填）
    status = Column(String(20), default="pending")         # pending/processing/done/failed
    is_enabled = Column(Integer, default=1)                 # 0=禁用 1=启用，控制是否参与RAG检索
    error_msg = Column(Text, nullable=True)                 # 失败原因
    created_at = Column(DateTime,default=utcnow, nullable=False)
    # ---- 知识库空间升级（阶段1，加列不删旧列；agent_id 仍保留给旧路径与 legacy 向量集合）----
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", name="fk_knowledge_space"), nullable=True)
    category = Column(String(60), nullable=True)            # 文档分类
    tags_json = Column(Text, nullable=True)                 # ["制度","2024"]
    version = Column(String(40), nullable=True)             # 用户自填版本号
    source_type = Column(String(20), nullable=False, default="upload")  # upload / web / import
    source_url = Column(String(1000), nullable=True)        # web 抓取来源
    updated_at = Column(DateTime, nullable=True)


class KnowledgeSpace(Base):
    """企业知识库空间：可复用的知识库容器，Agent 通过 agent_knowledge_space 绑定。

    阶段1 为用户级隔离（user_id = owner）；team_id / organization_id 为阶段6 预留。
    统计字段（doc_count / chunk_count / last_indexed_at）由后台任务异步回填，不实时算。
    """
    __tablename__ = "knowledge_spaces"
    __table_args__ = (
        Index("idx_kspace_user_status", "user_id", "status"),
        Index("idx_kspace_team", "team_id"),
        Index("idx_kspace_org", "organization_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_kspace_user"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    purpose = Column(String(60), nullable=True)             # customer_service / legal / product ...
    tags_json = Column(Text, nullable=True)
    is_enabled = Column(Integer, nullable=False, default=1)  # 0=停用 1=启用
    status = Column(String(20), nullable=False, default="active")   # active / archived
    doc_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    last_indexed_at = Column(DateTime, nullable=True)
    health_score = Column(Integer, nullable=True)           # 0~100，阶段5 回填
    health_json = Column(Text, nullable=True)
    # 迁移 / 企业预留
    legacy_agent_id = Column(Integer, nullable=True)        # 由某 Agent 私有库升级而来
    vector_migrated = Column(Integer, nullable=False, default=1)   # 0=检索需双读 legacy collection
    team_id = Column(Integer, nullable=True)
    organization_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AgentKnowledgeSpace(Base):
    """Agent ↔ 知识库空间 多对多绑定。"""
    __tablename__ = "agent_knowledge_space"
    __table_args__ = (
        Index("uq_agent_space", "agent_id", "space_id", unique=True),
        Index("idx_aks_space", "space_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_aks_agent"), nullable=False)
    space_id = Column(Integer, ForeignKey("knowledge_spaces.id", name="fk_aks_space"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RagDebugSample(Base):
    """知识库调试台：一次检索（可选带 LLM 回答）的完整快照。

    阶段4：用户在调试台跑一次检索后可「存为测试样例」，标注 useful/useless，
    勾选进评估集（in_eval_set=1）后可导出成 rag_eval 的 cases 喂给 /evaluation。
    """
    __tablename__ = "rag_debug_samples"
    __table_args__ = (
        Index("idx_rds_user_created", "user_id", "created_at"),
        Index("idx_rds_space", "space_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_rds_user"), nullable=False)
    space_id = Column(Integer, nullable=True)          # 单空间样例时记录；多空间留空
    space_ids_json = Column(Text, nullable=True)       # 实际检索用到的 space_id 列表
    agent_id = Column(Integer, nullable=True)          # 旧「Agent 私有库」调试时记录
    query = Column(Text, nullable=False)
    top_k = Column(Integer, nullable=True)
    rerank_enabled = Column(Integer, nullable=False, default=0)
    result_json = Column(Text, nullable=True)          # 命中 chunk / score / rerank / context / answer / citations 快照
    verdict = Column(String(10), nullable=True)        # useful / useless / null
    in_eval_set = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


# 知识块表（文档切分后的块，含向量库id引用）
class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        Index("idx_knowledge_chunk_knowledge_index", "knowledge_id", "chunk_index"),
        Index("idx_knowledge_chunk_vector_id", "vector_id"),
    )
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    knowledge_id = Column(Integer, ForeignKey("knowledge.id", name="fk_chunk_knowledge"), nullable=False)
    chunk_index = Column(Integer,default=0)
    content = Column(Text,nullable=False)
    vector_id = Column(String(100),nullable=False)#向量数据库
    token_count =Column(Integer,default=0)
    created_at = Column(DateTime,default=utcnow, nullable=False)
# Agent运行记录表（每次用户发消息=一次Run）
class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        Index("idx_agent_run_user_started", "user_id", "started_at"),
        Index("idx_agent_run_agent_started", "agent_id", "started_at"),
        Index("idx_agent_run_agent_conversation_started", "agent_id", "conversation_id", "started_at"),
        Index("idx_agent_run_status_started", "status", "started_at"),
    )
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id",name="fk_run_user"),nullable=False)
    agent_id = Column(Integer,ForeignKey("agent.id",name="fk_run_agent"),nullable=False)
    chat_id = Column(Integer,ForeignKey("chat.id",name="fk_run_chat"),nullable=True)
    user_message = Column(Text, nullable=False)            # 用户原始问题
    final_answer = Column(Text, nullable=True)             # 最终回答（失败时为null）
    status = Column(String(20), default="running")         # running/finished/failed/max_iter
    total_steps = Column(Integer, default=0)     # 总步数
    total_tokens = Column(Integer, default=0)              # 总token消耗
    error_msg = Column(Text, nullable=True)                # 失败原因
    started_at = Column(DateTime, default=utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)          # 结束时间（结束时回填）
    conversation_id = Column(Integer, ForeignKey("conversation.id", name="fk_run_conv", ondelete="SET NULL"),nullable=True)

# Agent运行步骤表（每一步的思考/工具/结果）
class AgentStep(Base):
    __tablename__ = "agent_step"
    __table_args__ = (
        Index("idx_agent_step_run_step", "run_id", "step_no"),
    )
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    run_id = Column(Integer, ForeignKey("agent_run.id", name="fk_step_run"), nullable=False)
    step_no = Column(Integer, nullable=False)  # 第几步（从1开始）
    step_type = Column(String(20), nullable=False)  # planner/tool/responder
    thought = Column(Text, nullable=True)  # LLM思考内容
    tool_name = Column(String(100), nullable=True)  # 调用了哪个工具
    tool_args = Column(Text, nullable=True)  # 工具参数（JSON字符串）
    tool_result = Column(Text, nullable=True)  # 工具返回结果
    tokens = Column(Integer, default=0)  # 本步token消耗
    created_at = Column(DateTime, default=utcnow, nullable=False)


class BackgroundTask(Base):
    __tablename__ = "background_task"
    __table_args__ = (
        Index("idx_background_task_user_status_created", "user_id", "status", "created_at"),
        Index("idx_background_task_user_type_created", "user_id", "task_type", "created_at"),
        Index("idx_background_task_status_type_next_run", "status", "task_type", "next_run_at", "created_at", "id"),
        Index("idx_background_task_status_type_created", "status", "task_type", "created_at", "id"),
        Index("idx_background_task_status_started", "status", "started_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_task_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_task_agent"), nullable=True)
    task_type = Column(String(50), nullable=False)
    # status: queued(排队) / running(执行中) / finished(成功) / failed(失败) / cancelled(已取消)
    status = Column(String(20), default="queued")
    title = Column(String(255), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    progress = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)  # queued 任务的最早可领取时间，用于失败后延迟重试
    # 重试机制：retry_count 记录本任务被重试过几次；parent_task_id 指向触发本次重试的原任务
    retry_count = Column(Integer, default=0, nullable=False)
    parent_task_id = Column(Integer, ForeignKey("background_task.id", name="fk_task_parent"), nullable=True)


class WebMonitor(Base):
    """用户网页监控项：记录 URL、检查状态和最近一次内容指纹。"""
    __tablename__ = "web_monitor"
    __table_args__ = (
        Index("idx_web_monitor_user_active", "user_id", "is_active"),
        Index("idx_web_monitor_user_checked", "user_id", "last_checked_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_web_monitor_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_web_monitor_agent"), nullable=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    interval_minutes = Column(Integer, default=30, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    last_status = Column(String(30), default="pending", nullable=False)
    last_hash = Column(String(64), nullable=True)
    last_title = Column(String(255), nullable=True)
    last_excerpt = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_change_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class OperationLog(Base):
    __tablename__ = "operation_log"
    __table_args__ = (
        Index("idx_operation_log_created", "created_at"),
        Index("idx_operation_log_user_created", "user_id", "created_at"),
        Index("idx_operation_log_method_created", "method", "created_at"),
        Index("idx_operation_log_status_created", "status_code", "created_at"),
        Index("idx_operation_log_latency_created", "latency_ms", "created_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_operation_log_user"), nullable=True)
    username = Column(String(255), nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    client_ip = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Skill(Base):
    __tablename__ = "skill"
    __table_args__ = (
        Index("idx_skill_user_id", "user_id"),
        Index("idx_skill_public", "is_public"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)      # 创建者
    name = Column(String(255), nullable=False)                            # 技能名
    description = Column(String(500))                                     # 描述
    config_file = Column(String(500), nullable=False)                     # YML路径
    is_public = Column(Integer, default=0)                                # 0=私有 1=公开
    created_at = Column(DateTime, default=utcnow)
    # 被哪些Agent使用（多对多） ← 新增这 3 行
    agents: Mapped[List["Agent"]] = relationship(
        secondary="agent_skill", lazy=False, back_populates="skills"
    )

# Agent-Skill 多对多关联(一个Agent可用多个Skill,一个Skill可被多个Agent用)
agent_skill = Table(
    "agent_skill",
    Base.metadata,
    Column("agent_id", Integer, ForeignKey("agent.id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skill.id"), primary_key=True)
)

# Memory 记忆表（长期记忆：会话摘要 + 关键事实）
class Memory(Base):
    __tablename__ = "memory"
    __table_args__ = (
        Index("idx_memory_user_agent_type_created", "user_id", "agent_id", "memory_type", "created_at"),
        Index("idx_memory_agent_id", "agent_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_memory_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_memory_agent"), nullable=False)
    memory_type = Column(String(20), nullable=False)  # summary=会话摘要, fact=关键事实
    content = Column(Text, nullable=False)
    chat_count = Column(Integer, default=0)  # 生成这条记忆时有多少轮对话
    created_at = Column(DateTime, default=utcnow, nullable=False)
# ========== 会话系统 ==========
class Conversation(Base):
    """会话表：一个 Agent 下可以有多个会话，每个会话包含多条消息"""
    __tablename__ = "conversation"
    __table_args__ = (
        Index("idx_conversation_user_agent_flags_time", "user_id", "agent_id", "is_archived", "is_pinned", "update_time"),
        Index("idx_conversation_user_time", "user_id", "update_time"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_conv_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_conv_agent"), nullable=False)
    title = Column(String(255), default="新会话")        # 会话标题（可由首条消息自动生成）
    is_pinned = Column(Integer, default=0)                # 0=普通 1=置顶
    is_archived = Column(Integer, default=0)              # 0=正常 1=归档
    create_time = Column(DateTime, default=utcnow, nullable=False)
    update_time = Column(DateTime, default=utcnow, nullable=False)  # 最后一条消息时间
    # 关联消息（一对多）
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",   # 删除会话时级联删除消息
        order_by="Message.create_time",  # 按时间排序
        lazy=True
    )

class Message(Base):
    """消息表：一个会话下的每条消息（user/assistant/system）"""
    __tablename__ = "message"
    __table_args__ = (
        Index("idx_message_conversation_time", "conversation_id", "create_time"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversation.id", name="fk_msg_conv"), nullable=False)
    role = Column(String(20), nullable=False)    # user / assistant / system
    content = Column(Text, nullable=False)
    create_time = Column(DateTime, default=utcnow, nullable=False)
    # 反向关联会话
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class UserWidget(Base):
    """用户自定义工作台小窗口。

    组件不保存前端源码，只保存一份「配置」：五段式 data_source / processor /
    view / trigger / actions，由统一的运行引擎（service/widgets/runner.py）执行、
    由前端统一渲染器按 view.kind 渲染。新增数据源/处理器/视图只需注册，不改主流程。
    """
    __tablename__ = "user_widgets"
    __table_args__ = (
        Index("idx_user_widgets_user_sort", "user_id", "sort_order"),
        Index("idx_user_widgets_next_run", "enabled", "next_run_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_user_widgets_user"), nullable=False)
    name = Column(String(120), nullable=False)
    type = Column(String(40), nullable=False)                 # 白名单组件类型
    description = Column(Text, nullable=True)
    spec_version = Column(Integer, nullable=False, default=1)  # 组件协议版本，便于日后升级兼容
    capabilities_json = Column(Text, nullable=True)            # ["fetch","schedule",...]
    data_source_json = Column(Text, nullable=True)             # {"kind": "...", "config": {...}}
    processor_json = Column(Text, nullable=True)
    view_json = Column(Text, nullable=True)
    trigger_json = Column(Text, nullable=True)
    actions_json = Column(Text, nullable=True)                 # ["refresh","edit","hide","delete"]
    enabled = Column(Integer, nullable=False, default=1)       # 0=隐藏 1=显示
    sort_order = Column(Integer, nullable=False, default=0)
    # 调度状态（P1 不单独建 widget_schedules 表，规则存在 trigger_json，运行状态放这里）
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), nullable=True)            # ok / error
    fail_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class WidgetDataPoint(Base):
    """组件每次运行的结果快照。

    payload_json 是通用结构，chart / table / metric / markdown 等各种展示形态
    都往里放；label / value / recorded_at 是通用快速查询字段（时间序列、趋势）。
    """
    __tablename__ = "widget_data_points"
    __table_args__ = (
        Index("idx_widget_data_points_widget_time", "widget_id", "recorded_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    widget_id = Column(Integer, ForeignKey("user_widgets.id", name="fk_widget_data_points_widget"), nullable=False)
    recorded_at = Column(DateTime, default=utcnow, nullable=False)
    ok = Column(Integer, nullable=False, default=1)            # 1=成功 0=失败
    label = Column(String(255), nullable=True)                # 例如 "1893.2 USD/oz"
    value = Column(Float, nullable=True)                      # 可用于快速取最新数值/画趋势
    payload_json = Column(Text, nullable=True)                # 完整结果，交给前端渲染器
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)


# 建表 / 幂等迁移 / 内置管理员初始化统一由 bootstrap_database() 触发，
# 不再在模块导入时执行——这样导入 ORM 模型、跑单测、执行离线脚本都不需要连库。
# 运行时由 FastAPI lifespan 和后台 Worker 启动时各调用一次。

# ========== 幂等迁移：为已存在的表补新增列（避免 ALTER TABLE 手动操作） ==========
def _run_migrations():
    """启动时自动执行的幂等迁移，仅列不存在时才加"""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    migrations = [
        # (表名, 列名, DDL)
        ("agent", "memory_enabled",
         "ALTER TABLE agent ADD COLUMN memory_enabled INT DEFAULT 1 COMMENT '0=关 1=开 长期记忆'"),
        ("agent_run", "conversation_id",
         "ALTER TABLE agent_run ADD COLUMN conversation_id INT NULL, ADD CONSTRAINT fk_run_conv FOREIGN KEY (conversation_id) REFERENCES conversation(id) ON DELETE SET NULL"),
        ("knowledge", "error_msg",
         "ALTER TABLE knowledge ADD COLUMN error_msg TEXT NULL COMMENT '知识库处理失败原因'"),
        ("knowledge", "is_enabled",
         "ALTER TABLE knowledge ADD COLUMN is_enabled INT DEFAULT 1 COMMENT '0=禁用 1=启用 是否参与RAG检索'"),
        ("conversation", "is_pinned",
         "ALTER TABLE conversation ADD COLUMN is_pinned INT DEFAULT 0 COMMENT '0=普通 1=置顶'"),
        ("conversation", "is_archived",
         "ALTER TABLE conversation ADD COLUMN is_archived INT DEFAULT 0 COMMENT '0=正常 1=归档'"),
        ("user", "is_disabled",
         "ALTER TABLE `user` ADD COLUMN is_disabled INT DEFAULT 0 COMMENT '0=启用 1=禁用'"),
        ("user", "last_login_at",
         "ALTER TABLE `user` ADD COLUMN last_login_at DATETIME NULL COMMENT '最后登录时间'"),
        ("user", "last_seen_at",
         "ALTER TABLE `user` ADD COLUMN last_seen_at DATETIME NULL COMMENT '最后访问时间'"),
        ("user", "phone",
         "ALTER TABLE `user` ADD COLUMN phone VARCHAR(20) NULL COMMENT '注册手机号', ADD UNIQUE KEY uq_user_phone (phone)"),
        ("background_task", "retry_count",
         "ALTER TABLE background_task ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数'"),
        ("background_task", "parent_task_id",
         "ALTER TABLE background_task ADD COLUMN parent_task_id INT NULL, ADD CONSTRAINT fk_task_parent FOREIGN KEY (parent_task_id) REFERENCES background_task(id)"),
        ("background_task", "next_run_at",
         "ALTER TABLE background_task ADD COLUMN next_run_at DATETIME NULL COMMENT '任务最早可领取时间，用于失败后延迟重试'"),
        ("user_profile", "auto_summary",
         "ALTER TABLE user_profile ADD COLUMN auto_summary TEXT NULL COMMENT 'AI自动提炼的用户画像'"),
        ("user_profile", "last_inferred_at",
         "ALTER TABLE user_profile ADD COLUMN last_inferred_at DATETIME NULL COMMENT '最近一次自动画像更新时间'"),
        # ---- 知识库空间升级（阶段1）----
        ("knowledge", "space_id",
         "ALTER TABLE knowledge ADD COLUMN space_id INT NULL COMMENT '所属知识库空间'"),
        ("knowledge", "category",
         "ALTER TABLE knowledge ADD COLUMN category VARCHAR(60) NULL COMMENT '文档分类'"),
        ("knowledge", "tags_json",
         "ALTER TABLE knowledge ADD COLUMN tags_json TEXT NULL COMMENT '文档标签'"),
        ("knowledge", "version",
         "ALTER TABLE knowledge ADD COLUMN version VARCHAR(40) NULL COMMENT '用户自填版本号'"),
        ("knowledge", "source_type",
         "ALTER TABLE knowledge ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'upload' COMMENT 'upload/web/import'"),
        ("knowledge", "source_url",
         "ALTER TABLE knowledge ADD COLUMN source_url VARCHAR(1000) NULL COMMENT 'web 抓取来源'"),
        ("knowledge", "updated_at",
         "ALTER TABLE knowledge ADD COLUMN updated_at DATETIME NULL COMMENT '最近更新时间'"),
        ("agent", "kb_top_k",
         "ALTER TABLE agent ADD COLUMN kb_top_k INT NOT NULL DEFAULT 5 COMMENT '知识库检索 top_k'"),
        ("agent", "kb_rerank_enabled",
         "ALTER TABLE agent ADD COLUMN kb_rerank_enabled INT NOT NULL DEFAULT 0 COMMENT '知识库检索是否 rerank'"),
        ("agent", "kb_force_citation",
         "ALTER TABLE agent ADD COLUMN kb_force_citation INT NOT NULL DEFAULT 1 COMMENT '回答强制带来源'"),
        ("agent", "kb_refuse_when_empty",
         "ALTER TABLE agent ADD COLUMN kb_refuse_when_empty INT NOT NULL DEFAULT 1 COMMENT '无命中时拒答'"),
    ]
    with engine.connect() as conn:
        for table, col, ddl in migrations:
            try:
                existing_cols = {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                # 表不存在，create_all 会处理，跳过
                continue
            if col not in existing_cols:
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                    print(f"[Migration] 已为 {table} 添加列 {col}")
                except Exception as e:
                    print(f"[Migration] 添加列 {col} 失败: {e}")

        # 列类型 / 约束变更（幂等：仅当当前不满足目标时才 MODIFY）
        column_type_migrations = [
            # (表, 列, 期望可空?, DDL)
            ("knowledge", "agent_id", True,
             "ALTER TABLE knowledge MODIFY COLUMN agent_id INT NULL"),
        ]
        for table, col, want_nullable, ddl in column_type_migrations:
            try:
                cols = {c["name"]: c for c in inspector.get_columns(table)}
            except Exception:
                continue
            info = cols.get(col)
            if info is None:
                continue
            if bool(info.get("nullable")) == bool(want_nullable):
                continue
            try:
                conn.execute(text(ddl))
                conn.commit()
                print(f"[Migration] 已调整 {table}.{col} 可空性 -> {want_nullable}")
            except Exception as e:
                print(f"[Migration] 调整 {table}.{col} 失败: {e}")

        index_migrations = [
            ("agent", "idx_agent_user_id_id", "CREATE INDEX idx_agent_user_id_id ON agent (user_id, id)"),
            ("llm_config", "idx_llm_config_user_model", "CREATE INDEX idx_llm_config_user_model ON llm_config (user_id, model_name)"),
            ("llm_config", "idx_llm_config_user_active", "CREATE INDEX idx_llm_config_user_active ON llm_config (user_id, is_active)"),
            ("chat", "idx_chat_user_agent_time", "CREATE INDEX idx_chat_user_agent_time ON chat (user_id, agent_id, create_time)"),
            ("knowledge", "idx_knowledge_user_created", "CREATE INDEX idx_knowledge_user_created ON knowledge (user_id, created_at)"),
            ("knowledge", "idx_knowledge_agent_created", "CREATE INDEX idx_knowledge_agent_created ON knowledge (agent_id, created_at)"),
            ("knowledge", "idx_knowledge_agent_enabled_status", "CREATE INDEX idx_knowledge_agent_enabled_status ON knowledge (agent_id, is_enabled, status)"),
            ("knowledge_chunk", "idx_knowledge_chunk_knowledge_index", "CREATE INDEX idx_knowledge_chunk_knowledge_index ON knowledge_chunk (knowledge_id, chunk_index)"),
            ("knowledge_chunk", "idx_knowledge_chunk_vector_id", "CREATE INDEX idx_knowledge_chunk_vector_id ON knowledge_chunk (vector_id)"),
            ("agent_run", "idx_agent_run_user_started", "CREATE INDEX idx_agent_run_user_started ON agent_run (user_id, started_at)"),
            ("agent_run", "idx_agent_run_agent_started", "CREATE INDEX idx_agent_run_agent_started ON agent_run (agent_id, started_at)"),
            ("agent_run", "idx_agent_run_agent_conversation_started", "CREATE INDEX idx_agent_run_agent_conversation_started ON agent_run (agent_id, conversation_id, started_at)"),
            ("agent_run", "idx_agent_run_status_started", "CREATE INDEX idx_agent_run_status_started ON agent_run (status, started_at)"),
            ("agent_step", "idx_agent_step_run_step", "CREATE INDEX idx_agent_step_run_step ON agent_step (run_id, step_no)"),
            ("background_task", "idx_background_task_user_status_created", "CREATE INDEX idx_background_task_user_status_created ON background_task (user_id, status, created_at)"),
            ("background_task", "idx_background_task_user_type_created", "CREATE INDEX idx_background_task_user_type_created ON background_task (user_id, task_type, created_at)"),
            ("background_task", "idx_background_task_status_type_created", "CREATE INDEX idx_background_task_status_type_created ON background_task (status, task_type, created_at, id)"),
            ("background_task", "idx_background_task_status_type_next_run", "CREATE INDEX idx_background_task_status_type_next_run ON background_task (status, task_type, next_run_at, created_at, id)"),
            ("background_task", "idx_background_task_status_started", "CREATE INDEX idx_background_task_status_started ON background_task (status, started_at)"),
            ("operation_log", "idx_operation_log_created", "CREATE INDEX idx_operation_log_created ON operation_log (created_at)"),
            ("operation_log", "idx_operation_log_user_created", "CREATE INDEX idx_operation_log_user_created ON operation_log (user_id, created_at)"),
            ("operation_log", "idx_operation_log_method_created", "CREATE INDEX idx_operation_log_method_created ON operation_log (method, created_at)"),
            ("operation_log", "idx_operation_log_status_created", "CREATE INDEX idx_operation_log_status_created ON operation_log (status_code, created_at)"),
            ("operation_log", "idx_operation_log_latency_created", "CREATE INDEX idx_operation_log_latency_created ON operation_log (latency_ms, created_at)"),
            ("skill", "idx_skill_user_id", "CREATE INDEX idx_skill_user_id ON skill (user_id)"),
            ("skill", "idx_skill_public", "CREATE INDEX idx_skill_public ON skill (is_public)"),
            ("memory", "idx_memory_user_agent_type_created", "CREATE INDEX idx_memory_user_agent_type_created ON memory (user_id, agent_id, memory_type, created_at)"),
            ("memory", "idx_memory_agent_id", "CREATE INDEX idx_memory_agent_id ON memory (agent_id)"),
            ("user_profile", "idx_user_profile_user_id", "CREATE INDEX idx_user_profile_user_id ON user_profile (user_id)"),
            ("user_workspace", "idx_user_workspace_user_id", "CREATE INDEX idx_user_workspace_user_id ON user_workspace (user_id)"),
            ("web_monitor", "idx_web_monitor_user_active", "CREATE INDEX idx_web_monitor_user_active ON web_monitor (user_id, is_active)"),
            ("web_monitor", "idx_web_monitor_user_checked", "CREATE INDEX idx_web_monitor_user_checked ON web_monitor (user_id, last_checked_at)"),
            ("conversation", "idx_conversation_user_agent_flags_time", "CREATE INDEX idx_conversation_user_agent_flags_time ON conversation (user_id, agent_id, is_archived, is_pinned, update_time)"),
            ("conversation", "idx_conversation_user_time", "CREATE INDEX idx_conversation_user_time ON conversation (user_id, update_time)"),
            ("message", "idx_message_conversation_time", "CREATE INDEX idx_message_conversation_time ON message (conversation_id, create_time)"),
        ]
        for table, index_name, ddl in index_migrations:
            try:
                existing_indexes = {idx["name"] for idx in inspector.get_indexes(table)}
            except Exception:
                continue
            if index_name not in existing_indexes:
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                    print(f"[Migration] 已为 {table} 添加索引 {index_name}")
                except Exception as e:
                    print(f"[Migration] 添加索引 {index_name} 失败: {e}")
# ========== 迁移结束 ==========
# 创建Session
SessionLocal = sessionmaker(bind=engine)


def _ensure_builtin_admin():
    """确保内置管理员账号存在，便于本地部署后直接进入后台。

    账号名/密码优先从环境变量 ADMIN_USERNAME / ADMIN_PASSWORD 读取。
    未配置密码时，默认用户名 admin，密码随机生成并打印一次，
    要求登录后立即修改，日志中不会再次出现。
    已存在的管理员账号不会在每次启动时被静默重置密码——
    只有显式设置 ADMIN_PASSWORD_RESET=true 并提供 ADMIN_PASSWORD 时，
    才会用它覆盖已有密码，用于找回丢失的管理员密码。
    """
    import bcrypt
    import secrets as _secrets

    admin_name = (os.getenv("ADMIN_USERNAME", "admin") or "admin").strip() or "admin"
    admin_password = (os.getenv("ADMIN_PASSWORD", "") or "").strip()
    force_reset = _env_bool("ADMIN_PASSWORD_RESET", False)

    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_name == "admin").first()
        if not role:
            role = Role(role_name="admin", description="系统管理员")
            db.add(role)
            db.flush()

        user = db.query(User).filter(User.name == admin_name).first()

        if not user:
            # 首次创建：未配置 ADMIN_PASSWORD 时生成随机密码，仅打印这一次。
            if not admin_password:
                admin_password = _secrets.token_urlsafe(12)
                print(
                    f"[Seed] 未配置 ADMIN_PASSWORD，已为管理员账号 {admin_name} "
                    f"生成随机初始密码：{admin_password}（请立即登录后台并修改，"
                    "该密码不会再次打印）"
                )
            hashed = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(name=admin_name, password=hashed, age=18)
            db.add(user)
            db.flush()
        else:
            # 账号已存在：默认不覆盖密码，避免把后台已改过的密码每次启动重置掉。
            # 仅当显式设置 ADMIN_PASSWORD_RESET=true 且提供了 ADMIN_PASSWORD 时才允许找回式重置。
            if force_reset and admin_password:
                user.password = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                print(f"[Seed] 已按 ADMIN_PASSWORD_RESET 重置管理员 {admin_name} 的密码")
            user.is_disabled = 0
            if user.age is None:
                user.age = 18

        if role not in (user.roles or []):
            user.roles.append(role)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Seed] 内置管理员初始化失败: {e}")
    finally:
        db.close()


_BOOTSTRAP_DONE = False


def bootstrap_database(*, seed_admin: bool = True, force: bool = False) -> None:
    """建表 + 幂等迁移 + 内置管理员初始化。

    运行时的唯一入口：由 FastAPI lifespan、后台 Worker 启动、以及
    `python -m models.init_db` 调用。进程内只会真正执行一次。

    可用环境变量 DB_AUTO_BOOTSTRAP=0 关闭（改由 Alembic 管理表结构的部署），
    此时仍可传 force=True 强制执行。
    """
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    if not force and not _env_bool("DB_AUTO_BOOTSTRAP", True):
        print("[Bootstrap] DB_AUTO_BOOTSTRAP=0，跳过自动建表/迁移")
        _BOOTSTRAP_DONE = True
        return

    Base.metadata.create_all(engine)
    _run_migrations()
    if seed_admin:
        _ensure_builtin_admin()
    _BOOTSTRAP_DONE = True


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # 允许离线执行：python -m models.init_db
    bootstrap_database(force=True)
    print("[Bootstrap] 建表与迁移完成")
