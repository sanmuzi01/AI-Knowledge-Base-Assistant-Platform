

"""
工具执行器：LangGraph ReAct 模式的组装工厂
职责：
  1. 创建 LLM Client（用 llm_adapter，用户Key隔离）
  2. 加载Agent绑定的Skill配置（用 skill_service）
  3. 只适配Skill包含的工具（用 tool_adapter，工具子集=Skill边界）
  4. 组装 ReActEngine 实例（LLM + 工具 + 图）
  5. 拼接system_prompt（Agent YML + Skill prompt）
  agent_runtime.py (编排层)
      ↓ 调 create_engine()
  ToolExecutor (本文件，组装工厂)
      ↓ 返回
  ReActEngine (引擎实例)
      ↓ 内部使用
  ChatOpenAI + LangChain Tools (只含Skill绑定的工具)
"""
from typing import Optional, List
from service.llm.langchain_adapter import create_langchain_llm
from service.tools.base import ToolContext
from service.tools.langchain_adapter import adapt_tools_by_names
from service.runtime.react_engine import ReActEngine
from prompt.prompt_manager import build_prompt
from service.skill_service import get_agent_skills_merged_config
from utils.logger_handler import get_logger

logger = get_logger("tool_executor")

class ToolExecutor:
    #ReAct 引擎组装工厂
    def __init__(self, db, user_id: int, agent_id: int, model_name: str,temperature: float = 0.7):
        self.db = db
        self.user_id = user_id
        self.agent_id = agent_id
        self.model_name = model_name


        # 1.创LLM(用户Key隔离+不同LLM支持）
        self.llm = create_langchain_llm(
            db=db,
            user_id=user_id,
            model_name=model_name,
            temperature=temperature,

        )

        # 2.读取 Agent的YML prompt
        agent_prompt = build_prompt(agent_id)
        # 3. 加载Agent绑定的Skill配置
        self.skill_config = get_agent_skills_merged_config(db, agent_id)
        # 4. 拼接完整system_prompt = Agent YML + Skill prompt
        skill_prompt = self.skill_config.get("system_prompt", "")
        if skill_prompt:
            self.system_prompt = f"{agent_prompt}\n\n{skill_prompt}"
        else:
            self.system_prompt = agent_prompt
        # 5.组装ToolContext
        self.ctx = ToolContext(
            llm_client=self.llm,
            user_id=user_id,
            agent_id=agent_id,
            system_prompt=self.system_prompt,
            permissions=self.skill_config.get("permissions", {}),
            resource_roots=self.skill_config.get("resource_roots", []),
        )

        # 6.只适配Skill包含的工具（工具子集=Skill业务边界）
        tool_names = self.skill_config.get("tool_names", [])
        if tool_names:
            self.lc_tools = adapt_tools_by_names(tool_names, ctx=self.ctx)
        else:
            # 没绑定Skill → 没有工具，Agent只能纯对话
            self.lc_tools = []
            logger.warning(f"Agent {agent_id} 未绑定任何Skill，将无工具可用")

        logger.info(
            f"ToolExecutor初始化完成: user={user_id}, agent={agent_id}, "
            f"model={model_name}, skills={self.skill_config.get('skill_names')}, "
            f"tools={len(self.lc_tools)}个"
        )
    def create_engine(self, max_iterations=5, step_callback=None) -> ReActEngine:
        engine = ReActEngine(
            llm=self.llm,
            tools=self.lc_tools,
            max_iterations=max_iterations,
            step_callback=step_callback,
            ctx=self.ctx,
        )
        logger.info(f"ReActEngine已创建: max_iter={max_iterations}, tools={len(self.lc_tools)}个")
        return engine
    def get_system_prompt(self) -> str:
        #获取完整system_prompt（Agent YML + Skill prompt）
        return self.system_prompt

    def get_skill_tool_defaults(self) -> dict:
        #获取Skill配置的工具默认值（预留：未来LLM没传参数时用默认值）
        return self.skill_config.get("tool_defaults_map", {})

    def list_available_tools(self) -> list:
        #列出已加载的工具名
        return [t.name for t in self.lc_tools]

    def get_permissions(self) -> dict:
        return self.skill_config.get("permissions", {})
