from typing import List
from typing import Generator

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
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
# 数据库连接
engine = create_engine(DATABASE_URL, echo=True)

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
    temperature = Column(Integer, default=70)                      # 温度参数（0-100，控制创造性）
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
#Base.metadata.drop_all(engine)
# 创建所有表
Base.metadata.create_all(engine)
# 创建Session
SessionLocal = sessionmaker(bind=engine)
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()