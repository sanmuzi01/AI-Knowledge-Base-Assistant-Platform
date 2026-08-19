"""
Skill Package 规范定义（阶段 A 产出物）
==========================================

【设计目标】
把 Skill 从"单个 YML 模板"升级为"标准化 Skill Package"。
Skill Package 是一个自描述、可导入导出、可版本化的目录，包含：
  - manifest.yaml   包元数据 + 工具声明 + 权限声明
  - SKILL.md        给 LLM 看的 Skill 说明（prompt 主体）
  - resources/      可选的参考资料（txt/md/pdf 等，运行时可读）

【目录结构】
skills_packages/
  └── {skill_uuid}/                    # 每个技能一个目录（用 skill_id 或 uuid 命名）
      ├── manifest.yaml                # 必填：元数据
      ├── SKILL.md                     # 必填：LLM 提示词主体
      └── resources/                   # 可选：参考资料
          ├── outline_template.txt
          └── ...

【manifest.yaml 字段规范】
name: str            必填  Skill 名称（展示用）
display_name: str    可选  展示名（缺省=name）
description: str     必填  一句话描述
version: str         必填  语义化版本号 (如 1.0.0)
author: str          可选  作者
license: str         可选  许可证 (MIT/Apache-2.0/...)
source: str          必填  来源标识 (template/blank/zip/github)
source_ref: str      可选  来源引用 (如 github url / 模板名)
tools:               必填  工具声明列表
  - name: str              工具名（必须能在平台 ToolRegistry 找到，否则校验失败）
    alias: str       可选  别名（外部 Skill 用别名 → 映射到平台工具）
    defaults: dict   可选  默认参数
    required: bool   可选  是否必须 (默认 false)
permissions:        可选  权限声明（安全沙箱用）
  network: bool           是否需要联网 (默认 false)
  file_read: list         允许读取的资源路径 (相对 resources/)
  exec: bool              是否包含可执行代码 (默认 false，外部 Skill 强制 false)
rag:                可选  RAG 知识库绑定
  knowledge_base_id: int  关联的知识库 ID
  top_k: int              检索条数 (默认 3)
constraints:        可选  约束说明（写到 SKILL.md 头部）
output_format: str  可选  期望输出格式 (text/markdown/json)

【SKILL.md 规范】
- Markdown 格式
- 主体是给 LLM 看的 system_prompt
- 运行时被 loader 读出来作为 Skill 的 system_prompt
- 比 YML 里的 system_prompt 字段更适合长文本、多段、含代码块的 prompt

【Canonical Skill 数据结构】
运行时统一表示，所有 Importer（template/blank/zip/github）输出的
Skill Package 经 Normalizer 处理后都转成这个结构，
Agent Runtime 只认这个结构，不关心来源。

【安全约束】
- 外部来源（zip/github）的 Skill 不允许包含 .py / .exe / .sh 等可执行文件
- tools 里的工具名必须在平台 ToolRegistry 中存在（或通过 alias 映射）
- 不允许 Skill 自带工具代码，所有工具由平台统一注册管理
- resources/ 中的文件运行时只读，且路径不能逃逸出 resources/
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillToolDecl:
    """manifest.yaml 中 tools 列表里的一项声明"""
    name: str                       # 平台工具名（或 alias 映射后的目标名）
    alias: Optional[str] = None     # 外部 Skill 用的别名 → 映射到 name
    defaults: dict = field(default_factory=dict)
    required: bool = False

    def resolve_to_platform_tool(self) -> str:
        """返回实际要调用的平台工具名
        alias 存在时用 alias 作为外部名，name 才是平台工具名；
        但运行时 ToolExecutor 只认平台工具名 name。
        """
        return self.name


@dataclass
class SkillPermissions:
    """权限声明：安全沙箱用，决定 Skill 运行时能做什么"""
    network: bool = False           # 是否允许联网
    file_read: list = field(default_factory=list)  # 允许读取的 resources 内相对路径
    exec: bool = False              # 是否含可执行代码（外部来源强制 False）


@dataclass
class SkillRagConfig:
    """RAG 知识库绑定配置"""
    knowledge_base_id: Optional[int] = None
    top_k: int = 3


@dataclass
class CanonicalSkill:
    """Canonical Skill：所有来源的 Skill Package 标准化后的运行时表示

    生命周期：
        Source(template/blank/zip/github)
          → Importer 读取
          → Validator 校验（格式 + 工具兼容 + 安全）
          → Normalizer 转换
          → CanonicalSkill（本类）
          → 存入 skill_packages/{id}/ 目录
          → 数据库 skill 表存元数据 + package_path
          → Agent Runtime 加载 → ToolExecutor 执行
    """
    # ===== 元数据 =====
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    license: str = ""
    source: str = "blank"           # template/blank/zip/github
    source_ref: str = ""            # 模板名 / github url / 上传文件名

    # ===== 工具声明 =====
    tools: list[SkillToolDecl] = field(default_factory=list)

    # ===== 权限 =====
    permissions: SkillPermissions = field(default_factory=SkillPermissions)

    # ===== RAG 配置 =====
    rag: Optional[SkillRagConfig] = None

    # ===== Prompt + 资源 =====
    system_prompt: str = ""         # 从 SKILL.md 读取
    constraints: str = ""
    output_format: str = "text"

    # ===== 存储路径 =====
    package_path: str = ""          # skill_packages/{id}/ 绝对路径


    # ===== 运行时辅助方法 =====
    def get_tool_names(self) -> list[str]:
        """返回所有工具的平台名列表（ToolExecutor 过滤用）"""
        return [t.name for t in self.tools]

    def get_tool_defaults_map(self) -> dict[str, dict]:
        """返回 {工具名: 默认参数} 映射"""
        return {t.name: t.defaults for t in self.tools}

    def to_merged_prompt(self) -> str:
        """合并 system_prompt + constraints（Agent Runtime 用）"""
        parts = []
        if self.constraints:
            parts.append(f"【约束】\n{self.constraints}")
        if self.system_prompt:
            parts.append(self.system_prompt)
        return "\n\n".join(parts)


@dataclass
class SkillValidationResult:
    """Skill Package 校验结果"""
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)
