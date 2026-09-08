"""Skill 业务层子模块（原 service/skill_service.py 拆分而来）。

对外统一入口仍是 service/skill_service.py，这里只是内部实现细分：
- common.py          共享的小工具函数（命名、dict 转换、权限归一化等）
- validation.py      Skill 配置文件与工具名校验
- crud.py            Skill 的增删改查
- import_export.py   Skill 导入（yml/zip 包）与导出
- templates.py       Skill 模板的增删改查
- binding.py         Skill 与 Agent 的绑定/解绑、合并配置

不建议业务代码直接从这些子模块 import；请继续从 service.skill_service import，
保持对外接口不变。
"""
