"""
工具适配器：把自定义 BaseTool 适配成 LangChain BaseTool
LangGraph 期望的工具是 langchain_core.tools.BaseTool
我们的工具是 service.tools.base.BaseTool
两者接口不同，必须适配
1. 把自定义工具的 name/description/parameters 翻译成 LangChain 格式
2. 在执行时，如果工具 requires_context=True，自动注入 ToolContext
3. 保留我们所有的用户隔离/Key隔离/prompt覆盖机制
"""
from typing import Any,List,Optional,Dict,Type
from pydantic import BaseModel, create_model
from langchain_core.tools import BaseTool as LCBaseTool, StructuredTool
from service.tools.base import BaseTool, ToolContext, ToolPermissionError
from utils.logger_handler import get_logger
logger = get_logger("tool_adapter")
#JSON Schema类型 →Python类型映射
_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}
def _json_type_to_python(json_type: Optional[str]) -> type:
    """把JSONSchema的type转成 Python 类型"""
    if not json_type:
        return str
    return _JSON_TYPE_MAP.get(json_type, str)
def create_args_schema(parameters: dict) -> Optional[Type[BaseModel]]:
    """从自定义工具的 parameters(JSON Schema) 动态创建 Pydantic Model
    LangChain BaseTool 需要 args_schema 来告诉 LLM 工具接受什么参数
    """
    if not parameters or parameters.get("type") != "object":
        return None
    props = parameters.get("properties", {})
    if not props:
        return None
    required_fields = set(parameters.get("required", []))
    fields = {}
    for name, prop in props.items():
        py_type = _json_type_to_python(prop.get("type"))
        # required 字段用 ... (必填)，非 required 用 None (可选)
        if name in required_fields:
            fields[name] = (py_type, ...)
        else:
            # 带默认值的字段
            default_val = prop.get("default", None)
            fields[name] = (Optional[py_type], default_val)
    return create_model("ToolArgsSchema", **fields) if fields else None
def adapt_tool(custom_tool: BaseTool, ctx: Optional[ToolContext] = None) -> LCBaseTool:
    """把单个自定义工具适配成 LangChain BaseTool
    :param custom_tool: 自定义工具实例(已实例化)
    :param ctx: 工具上下文(requires_context=True 的工具需要)
                传 None 则只适配无状态工具(requires_context=False)
    :return: LangChain BaseTool 实例"""
    args_schema = create_args_schema(custom_tool.parameters)
    tool_name = custom_tool.name
    tool_desc = custom_tool.description
    # 如果工具需要上下文，但没传 ctx → 报错(防止后续执行时崩溃)
    if custom_tool.requires_context and ctx is None:
        raise ValueError(
            f"工具 '{tool_name}' requires_context=True，必须传入 ToolContext"
        )
    # 构造执行函数：闭包捕获 custom_tool 和 ctx
    def _run(**kwargs) -> str:
        # requires_context 的工具注入 ctx
        if ctx is not None:
            custom_tool.set_context(ctx)
        try:
            custom_tool.check_permissions()
        except ToolPermissionError as e:
            logger.warning(f"[LangChain适配] 工具权限拒绝: {tool_name}, error={e}")
            return f"工具权限不足: {e}"
        logger.info(f"[LangChain适配] 执行工具: {tool_name}, 参数: {kwargs}")
        return custom_tool.execute(**kwargs)
    # 用 Tool 类包装(最简单的 LangChain BaseTool 子类)
    lc_tool = StructuredTool.from_function(
        name=tool_name,
        description=tool_desc,
        func=_run,
        args_schema=args_schema,
    )
    logger.info(f"[LangChain适配] 适配工具: {tool_name} → LangChain StructuredTool")
    return lc_tool
def adapt_all_tools(ctx: Optional[ToolContext] = None) -> List[LCBaseTool]:
    """把 ToolRegistry 里所有工具适配成 LangChain BaseTool 列表
    用途：一次性把所有已注册工具转成 LangGraph 能用的格式
    传给 create_react_agent(model, tools=adapt_all_tools(ctx), ...)
    :param ctx: 工具上下文(requires_context=True 的工具需要)
              无状态工具不需要 ctx 也能适配
    :return: LangChain BaseTool 列表
    """
    from service.tools.base import ToolRegistry
    custom_tools = ToolRegistry.get_all_tools()  # 拿到所有自定义工具实例
    lc_tools = []
    for custom_tool in custom_tools:
        try:
            lc_tool = adapt_tool(custom_tool, ctx)
            lc_tools.append(lc_tool)
        except ValueError as e:
            # requires_context=True 但没传 ctx → 跳过并警告
            logger.warning(f"跳过工具 '{custom_tool.name}': {e}")
        except Exception as e:
            logger.error(f"适配工具 '{custom_tool.name}' 失败: {e}")
    logger.info(f"[LangChain适配] 共适配 {len(lc_tools)}/{len(custom_tools)} 个工具")
    return lc_tools


def adapt_tools_by_names(tool_names: List[str], ctx: Optional[ToolContext] = None) -> List[LCBaseTool]:
    """按工具名列表适配（只适配指定的工具，不是全部）
    用途：Skill系统用。ToolExecutor从merged_config拿到tool_names后，
          只适配这些工具，不是ToolRegistry里的所有工具。
    tool_names: 要加载的工具名列表，如 ["outline_generator", "word_count"]
    ctx: 工具上下文
    :return: LangChain BaseTool 列表"""
    from service.tools.base import ToolRegistry
    lc_tools = []
    for name in tool_names:
        tool_class = ToolRegistry.get(name)
        if tool_class is None:
            logger.warning(f"工具 '{name}' 未注册，跳过")
            continue
        try:
            custom_tool = tool_class()
            lc_tool = adapt_tool(custom_tool, ctx)
            lc_tools.append(lc_tool)
        except Exception as e:
            logger.error(f"适配工具 '{name}' 失败: {e}")
    logger.info(f"[LangChain适配] 按名适配 {len(lc_tools)}/{len(tool_names)} 个工具")
    return lc_tools
