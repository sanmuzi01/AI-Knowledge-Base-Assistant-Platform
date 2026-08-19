from typing import List
from typing import Generator
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, relationship
from dotenv import load_dotenv
import os

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
# 数据库连接
engine = create_engine(DATABASE_URL, echo=False)

# ORM基类
Base = declarative_base()
# 用户角色关联表
association_table = Table(
    "user_role",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id"),primary_key=True),
    Column("role_id", Integer, ForeignKey("role.id"),primary_key=True)
)
#class UserRole(Base):
#    __tablename__ = "user_role"
#   id = Column(Integer,primary_key=True,autoincrement=True)
#    user_id = Column(Integer,ForeignKey("user.id"))
#   role_id = Column(Integer,ForeignKey("role.id"))
# 用户表
class User(Base):
    __tablename__ = "user"
    id = Column(Integer,primary_key=True,autoincrement=True)
    name = Column(String(255),nullable=False,unique=True)
    password = Column(String(255),nullable=False)
    age = Column(Integer)
    is_disabled = Column(Integer, default=0)
    last_login_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    selected_agent_id = Column(Integer,ForeignKey("agent.id", name="fk_user_selected_agent"),nullable=True)    #关联关系
    roles:Mapped[List["Role"]]=relationship(secondary=association_table,lazy=False,back_populates="users")
    #1对1的关系
    #role = relationship("Role",lazy=False,back_populates="user")
# 智能体表
class Agent(Base):
    __tablename__ = "agent"
    id = Column(Integer,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id", name="fk_agent_user"),nullable=False)
    name = Column(String(255),nullable=False)
    # Prompt文件路径
    prompt_file = Column( String(255),nullable=True)
    model_name = Column(String(100), default="glm-4")             # 用的大模型
    rag_enabled = Column(Integer, default=0)                       # 是否启用RAG（0=否，1=是）
    memory_enabled = Column(Integer, default=1)                    # 是否启用长期记忆（0=否，1=是）
    temperature = Column(Integer, default=70)                      # 温度参数（0-100，控制创造性）
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    model_name = Column(String(100), nullable=False)  # "glm-4" / "gpt-4o" / "deepseek-chat"
    api_key = Column(String(500), nullable=False)      # 用户填写的 API Key（加密存储）
    api_url = Column(String(500))                      # 可选，自定义端点
    is_active = Column(Integer, default=1)             # 0=停用, 1=启用
# 聊天记录表
class Chat(Base):
    __tablename__ = "chat"
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
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    user_id = Column(Integer,ForeignKey("user.id",name="fk_knowledge_user"),nullable=False)
    agent_id = Column(Integer,ForeignKey("agent.id",name="fk_knowledge_agent"),nullable=False)
    file_name = Column(String(255),nullable=False) # 原始文件名
    file_path = Column(String(500),nullable=False) #磁盘存储路径
    file_type = Column(String(50),nullable=False) # pdf/docx/txt/md
    file_size = Column(Integer,default=0) # 字节数
    chunk_count =Column(Integer,default=0) # 切块数（解析后回填）
    status = Column(String(20), default="pending")         # pending/processing/done/failed
    error_msg = Column(Text, nullable=True)                 # 失败原因
    created_at = Column(DateTime,default=datetime.utcnow, nullable=False)
# 知识块表（文档切分后的块，含向量库id引用）
class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    knowledge_id = Column(Integer, ForeignKey("knowledge.id", name="fk_chunk_knowledge"), nullable=False)
    chunk_index = Column(Integer,default=0)
    content = Column(Text,nullable=False)
    vector_id = Column(String(100),nullable=False)#向量数据库
    token_count =Column(Integer,default=0)
    created_at = Column(DateTime,default=datetime.utcnow, nullable=False)
# Agent运行记录表（每次用户发消息=一次Run）
class AgentRun(Base):
    __tablename__ = "agent_run"
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
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)          # 结束时间（结束时回填）
    conversation_id = Column(Integer, ForeignKey("conversation.id", name="fk_run_conv", ondelete="SET NULL"),nullable=True)

# Agent运行步骤表（每一步的思考/工具/结果）
class AgentStep(Base):
    __tablename__ = "agent_step"
    id  = Column(Integer ,primary_key=True,autoincrement=True)
    run_id = Column(Integer, ForeignKey("agent_run.id", name="fk_step_run"), nullable=False)
    step_no = Column(Integer, nullable=False)  # 第几步（从1开始）
    step_type = Column(String(20), nullable=False)  # planner/tool/responder
    thought = Column(Text, nullable=True)  # LLM思考内容
    tool_name = Column(String(100), nullable=True)  # 调用了哪个工具
    tool_args = Column(Text, nullable=True)  # 工具参数（JSON字符串）
    tool_result = Column(Text, nullable=True)  # 工具返回结果
    tokens = Column(Integer, default=0)  # 本步token消耗
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BackgroundTask(Base):
    __tablename__ = "background_task"
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    # 重试机制：retry_count 记录本任务被重试过几次；parent_task_id 指向触发本次重试的原任务
    retry_count = Column(Integer, default=0, nullable=False)
    parent_task_id = Column(Integer, ForeignKey("background_task.id", name="fk_task_parent"), nullable=True)


class Skill(Base):
    __tablename__ = "skill"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)      # 创建者
    name = Column(String(255), nullable=False)                            # 技能名
    description = Column(String(500))                                     # 描述
    config_file = Column(String(500), nullable=False)                     # YML路径
    is_public = Column(Integer, default=0)                                # 0=私有 1=公开
    created_at = Column(DateTime, default=datetime.utcnow)
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_memory_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_memory_agent"), nullable=False)
    memory_type = Column(String(20), nullable=False)  # summary=会话摘要, fact=关键事实
    content = Column(Text, nullable=False)
    chat_count = Column(Integer, default=0)  # 生成这条记忆时有多少轮对话
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
# ========== 会话系统 ==========
class Conversation(Base):
    """会话表：一个 Agent 下可以有多个会话，每个会话包含多条消息"""
    __tablename__ = "conversation"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_conv_user"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agent.id", name="fk_conv_agent"), nullable=False)
    title = Column(String(255), default="新会话")        # 会话标题（可由首条消息自动生成）
    is_pinned = Column(Integer, default=0)                # 0=普通 1=置顶
    is_archived = Column(Integer, default=0)              # 0=正常 1=归档
    create_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    update_time = Column(DateTime, default=datetime.utcnow, nullable=False)  # 最后一条消息时间
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversation.id", name="fk_msg_conv"), nullable=False)
    role = Column(String(20), nullable=False)    # user / assistant / system
    content = Column(Text, nullable=False)
    create_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 反向关联会话
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


#Base.metadata.drop_all(engine)
# 创建所有表
Base.metadata.create_all(engine)

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
        ("background_task", "retry_count",
         "ALTER TABLE background_task ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数'"),
        ("background_task", "parent_task_id",
         "ALTER TABLE background_task ADD COLUMN parent_task_id INT NULL, ADD CONSTRAINT fk_task_parent FOREIGN KEY (parent_task_id) REFERENCES background_task(id)"),
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
_run_migrations()
# ========== 迁移结束 ==========
# 创建Session
SessionLocal = sessionmaker(bind=engine)


def _ensure_builtin_admin():
    """确保内置管理员账号存在，便于本地部署后直接进入后台。"""
    import bcrypt

    admin_name = "admin"
    admin_password = "139218"
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_name == "admin").first()
        if not role:
            role = Role(role_name="admin", description="系统管理员")
            db.add(role)
            db.flush()

        user = db.query(User).filter(User.name == admin_name).first()
        hashed = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        if not user:
            user = User(name=admin_name, password=hashed, age=18)
            db.add(user)
            db.flush()
        else:
            user.password = hashed
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


_ensure_builtin_admin()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
