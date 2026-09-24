"""单企业私有化部署的统一能力开关。

Step 0（企业化改造前的安全收口）要求：把"要不要开放某项能力给普通用户"这个判断集中
在一处，后端路由强制执行、前端读同一个语义决定要不要显示入口——不要在每个路由里
各自 `os.getenv(...)` 一遍，容易漏改、也没法一眼看出现在到底开了哪些口子。

当前只登记了一个开关；以后再收紧/放开别的能力，照这个模式加一个函数，
不要绕回散落的 os.getenv。
"""
import os


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def user_api_connectors_enabled() -> bool:
    """普通用户能否自己给 Agent 创建企业接口连接器。

    默认关闭：单企业私有化部署下，"能不能接入外部系统"应该是管理员审核后统一配置的
    能力，不是员工自助接的——即便请求地址本身仍然会过 SSRF 校验（这里管的是"能不能配"
    这一步，不是"配了会不会被滥用"那一步，两者都要）。
    需要放开给普通用户自助配置（例如个人 demo / 评估环境）时显式设
    `FEATURE_USER_API_CONNECTORS=true`。
    """
    return _flag("FEATURE_USER_API_CONNECTORS")
