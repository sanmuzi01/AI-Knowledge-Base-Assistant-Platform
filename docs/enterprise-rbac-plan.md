# 企业化数据模型与授权层设计稿（Phase 3B / 3C 评审用）

状态：**设计稿，未落地**。本文档只是数据模型 + 路由改造范围的评审材料，Phase 3A
（Alembic 权威化）完成、这份稿子评审通过后才动迁移和代码——按既定顺序，不提前改表。

## 0. 现状：不是从零开始

核对了一遍现有代码，企业化改造要用到的几块地基已经预留了，设计时要接上，不要重建：

| 预留位置 | 现状 |
|---|---|
| `KnowledgeSpace.team_id` / `KnowledgeSpace.organization_id`（[models/init_db.py:258](../models/init_db.py:258)） | 字段已经在，注释写"阶段6预留"，一直是 `nullable`、未使用 |
| `SpaceMember`（[models/init_db.py:303](../models/init_db.py:303)） | 空间级三档角色 admin/editor/viewer，已在用，语义就是本文档"三层不合并"里的第三层 |
| `KbAuditLog`（[models/init_db.py:322](../models/init_db.py:322)） | 知识库空间/文档/成员/绑定的写操作审计表，已建但看起来还没接线——企业化的审计需求可以直接扩展这张表，不用新建 |
| `Role` + `is_admin_user()`（[service/admin_service.py:37](../service/admin_service.py:37)） | 目前是"平台全局管理员"判断：角色表命中 `ADMIN_ROLE_NAMES` 或用户名落在 `ADMIN_USER_NAMES`。这条要继续保留，但只管平台超管，企业内部的权限判断迁到新的授权层（见第 2 节） |

## 1. 数据模型

### 1.1 命名：不新增 Department

```
Organization = 企业（单企业部署下，这张表长期只会有 1 行，但结构按可扩展设计）
Team         = 部门（前端一律显示"部门"，代码/表名统一用 Team，不出现 department_id）
```

### 1.2 新表

```python
class Organization(Base):
    __tablename__ = "organization"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active / disabled
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Team(Base):
    __tablename__ = "team"
    __table_args__ = (
        Index("idx_team_org", "organization_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organization.id", name="fk_team_org"), nullable=False)
    name = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        Index("uq_org_member", "organization_id", "user_id", unique=True),
        Index("idx_org_member_user", "user_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organization.id", name="fk_om_org"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_om_user"), nullable=False)
    role = Column(String(20), nullable=False, default="member")   # owner / admin / auditor / member
    status = Column(String(20), nullable=False, default="active")  # active / disabled
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        Index("uq_team_member", "team_id", "user_id", unique=True),
        Index("idx_team_member_user", "user_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("team.id", name="fk_tm_team"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_tm_user"), nullable=False)
    role = Column(String(20), nullable=False, default="member")   # admin / editor / member
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
```

`status` 字段（而不是直接删行）是为了停用成员时保留审计痕迹，跟 `KnowledgeSpace.status`
（active/archived）的既有风格一致。

### 1.3 三层权限语义不同，不合并

```
OrganizationMember.role  → 能不能管理"企业"这个范围（成员、企业级模型配置、企业审计）
TeamMember.role          → 能不能管理"部门"这个范围（部门知识库、部门助手、部门成员）
SpaceMember.role         → 能不能访问"某一个具体知识库空间"（现有表，继续保留原样）
```

不合并的理由：一个部门管理员不代表能访问该部门下所有知识库空间（空间可能标了
`visibility=private` 只给创建者+被邀请的人），一个知识库空间的 `editor` 也不代表
对这个部门有任何管理权。三层各自独立判断，缺一层就在那一层拒绝。

### 1.4 现有表补外键

```
Team.organization_id            → 已在上面新表里，非空
KnowledgeSpace.organization_id  → 已存在字段，改为在应用层强制非空写入（企业化上线后）
KnowledgeSpace.team_id          → 已存在字段，同上
```

写入时的强制校验：`KnowledgeSpace.team_id` 对应的 `Team.organization_id` 必须等于
`KnowledgeSpace.organization_id`——不允许把一个空间挂到"别的企业的部门"下面。这条校验
放进 service 层（`knowledge_space_service` 的创建/转移入口），不指望数据库约束覆盖跨表条件。

### 1.5 迁移顺序（依赖 Phase 3A 先把 Alembic 权威化做完）

1. 建 `organization` / `team` / `organization_members` / `team_members` 四张新表（互不影响现有数据，纯新增）。
2. 数据回填：为当前部署创建 1 行 `Organization`（"默认企业"），把所有现有用户批量插入
   `organization_members`（role=member，已有平台管理员的 role=owner）——这一步是数据迁移脚本，
   不是 schema 迁移，要单独写、要能重复执行不出错（幂等）。
3. `KnowledgeSpace.organization_id` 批量回填成默认企业 id（现有数据全部挂到默认企业下，不建
   `Team`、`team_id` 留空——没有部门信息，不能瞎猜）。
4. 上面三步全部落地、跑过一遍全新空库 `alembic upgrade head` 验证后，才开始第 3 节的路由改造。

## 2. 统一授权层

新建 `service/enterprise_access.py`（暂定名，评审时可改），对外只暴露这几个函数，
路由层直接 `Depends`，不再各自手写判断：

```python
def require_org_role(*roles: str):
    """FastAPI 依赖工厂：当前用户必须是这个企业的成员，且角色在 roles 里，否则 403。"""

def require_team_role(*roles: str):
    """同上，范围换成部门；如果部门不属于当前用户所在企业，视为不存在（404，不是 403——
    不暴露"这个部门存在但你无权"这条信息）。"""

def require_space_permission(min_role: str):
    """检查具体知识库空间的 SpaceMember.role 是否满足最低要求（viewer < editor < admin），
    owner（KnowledgeSpace.user_id）视为高于 admin。"""

def get_accessible_space_ids(db, user) -> list[int]:
    """给检索/列表接口用：当前用户能看到哪些知识库空间 id
    （自己 owner 的 + SpaceMember 命中的 + 所属部门公开的），一次查出来，
    不要在业务代码里现算三种来源再拼 OR。"""
```

### 2.1 校验顺序（固定，不因路由而变）

```
1. 是否属于该企业（organization_members 有效行）
2. 是否具有所需的组织/部门角色
3. 是否拥有该具体资源的访问权限（SpaceMember 或资源自身的 owner 字段）
4. 是否允许当前这个操作（比如 viewer 不能删除文档）
```

第 1、2 步不通过统一走 404（不暴露资源/部门存在性）；第 3、4 步不通过走 403
（已经确认资源存在，只是没权限，这条信息本身不敏感）。这跟现有
`test_cross_user_access_is_not_found_not_forbidden` 类测试的既有约定一致，改造时延续，不新发明一套。

### 2.2 与 `is_admin_user()` 的关系

`is_admin_user()`（[service/admin_service.py:37](../service/admin_service.py:37)）**只保留给平台超级管理员**
（运维这套系统本身的人，理论上单企业部署下这个角色几乎不出现在业务操作里）。
企业内部的所有权限判断——包括原来很多路由里"没有专门权限模型，索性判断
`is_admin_user()` 顶替"的地方——迁移到 `require_org_role`/`require_team_role`。
这是本次改造里最容易漏改的一步，第 3 节按模块清点。

## 3. 逐模块改造范围清单

**说明**：下面的路由数是对各 `FasdtApi/*.py` 文件按 `@router.get/post/put/patch/delete`
计数得到的规模参考，用来定改造顺序和工作量，**不是逐条读过之后的审阅结论**——具体每个
路由要不要加、加哪一层校验，要在改那个模块时单独过一遍，不能照这张表机械套用。

| 顺序 | 模块 | 涉及文件 | 路由数（规模参考） | 备注 |
|---|---|---|---|---|
| 1 | 知识库和文件下载 | `knowledge.py`、`knowledge_space.py`、`attachment_route.py` | 14 + 17 + 3 = 34 | 风险最高：文档下载直接触达内容，`get_accessible_space_ids` 先在这里落地 |
| 2 | Agent 及其知识库绑定 | `agent.py`、`agent_pipeline.py`、`agent_run.py` | 18 + 5 + 2 = 25 | Agent 绑定的空间必须是当前用户"可访问"的空间，不能绑定别企业/别部门的私有空间 |
| 3 | Skill | `skill_route.py` | 25 | 创建/编辑/删除已经是平台管理员专属（见 [docs/testing.md](testing.md) Step 0 章节），这里主要是"官方 Skill 发布"要不要分部门维度，需要跟 Phase 3D 一起定 |
| 4 | 模型配置 | `llm_config.py` | 6 | 要接住"企业统一模型配置"这条业务需求（Phase 3D），但访问权限先按 `require_org_role` 收紧 |
| 5 | 外部连接器 | `agent.py` 里的 `api-connectors` 路由（本次 Step 0 已加管理员/开关校验，见 [docs/testing.md](testing.md)） | 4 | Step 0 已经先做了一道粗粒度收紧；这里再叠加部门维度是 Phase 3D 的事，不用现在动 |
| 6 | 后台任务、统计与审计 | `background_task.py`、`evaluation.py`、`rag_debug.py`、`admin.py` 里的统计/审计部分 | 5 + 8 + 6 + 21 | 优先扩展现成的 `KbAuditLog`，不新建一套审计表 |

## 4. 需要用户决策的开放问题

1. **是否真的需要"多企业"数据模型？** 你的方案本身是"单企业私有化部署"——一个部署只服务
   一家企业。`Organization` 表按可扩展设计（为未来 SaaS 化留门），但 v1 只会有 1 行数据，
   `require_org_role` 的"是否属于该企业"这一步在单企业场景下永远为真。这层校验现在就做，
   还是先跳过（只做 Team 这一层），等真的要多企业时再补？跳过能省一次迁移和一层判断，
   但以后要补时是数据回填 + 全路由改造，不是加一个字段那么简单。
2. **`organization_members`/`team_members` 的 `role` 用字符串枚举还是新建 Role 表外键？**
   现有 `SpaceMember.role` 是字符串（"admin"/"editor"/"viewer"），本文档为保持一致也用了字符串。
   字符串简单但没有数据库级约束防拼错；如果你们后续想让角色可配置（比如企业自定义角色名），
   现在就该换成外键表，返工成本比现在改一次小得多。
3. **部门管理员能不能看到部门下所有知识库空间，即使自己不是那个空间的 `SpaceMember`？**
   这决定 `get_accessible_space_ids` 的第三个来源要不要加"我是这个空间所属部门的
   team admin"。方案原文没写清楚，需要你确认。

## 5. 这份设计稿评审通过后，下一步

按 Phase 3A → 3B → 3C 顺序：
1. Phase 3A（Alembic 权威化）先完成——**这份文档不依赖它，但迁移执行要等它**。
2. 针对第 4 节的三个问题给出决策。
3. 我据此把 1.2 节的表结构定稿，出 Alembic 迁移文件 + 第 1.5 节的数据回填脚本 + 幂等性测试。
4. 授权层（第 2 节）先落地 `require_org_role`/`require_team_role`/`require_space_permission`/
   `get_accessible_space_ids` 四个函数和它们自己的单元测试，再按第 3 节的顺序逐模块接入、
   每接入一个模块跑一遍那个模块的路由级测试确认没有意外放宽或收紧权限。
