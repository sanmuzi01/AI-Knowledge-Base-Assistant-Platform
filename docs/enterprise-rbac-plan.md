# 企业化数据模型与授权层设计稿（Phase 3B / 3C 评审用）

状态：**设计已定稿，尚未动表**。Phase 3A（Alembic 权威化）已经完成（见
[docs/db-migration-plan.md](db-migration-plan.md) 第 5 节），这份文档的表结构设计也
定稿了——下一步是真的写迁移文件和授权层代码，还没开始动手。

## 0. 现状：不是从零开始（本节 2026-09-24 二次核对后更正过一次）

核对了一遍现有代码，企业化改造要用到的几块地基已经预留了，设计时要接上，不要重建：

| 预留位置 | 现状 |
|---|---|
| `Organization` / `Team`（[models/init_db.py:367](../models/init_db.py:367)/[376](../models/init_db.py:376)，表名 `organizations`/`teams`） | **已经是真实存在的表**，本文档最初的草稿漏看了这两个类，一度设计了同概念的新表——已改成扩展这两张表，不新建，见 1.2 节 |
| `KnowledgeSpace.team_id` / `KnowledgeSpace.organization_id`（[models/init_db.py:258](../models/init_db.py:258)） | 字段已经在，注释写"阶段6预留"，一直是 `nullable`、未使用 |
| `SpaceMember`（[models/init_db.py:303](../models/init_db.py:303)） | 空间级三档角色 admin/editor/viewer，已在用，语义就是本文档"三层不合并"里的第三层 |
| `KbAuditLog`（[models/init_db.py:322](../models/init_db.py:322)） | 知识库空间/文档/成员/绑定的写操作审计表，已建但看起来还没接线——企业化的审计需求可以直接扩展这张表，不用新建 |
| `Role` + `is_admin_user()`（[service/admin_service.py:37](../service/admin_service.py:37)） | 目前是"平台全局管理员"判断：角色表命中 `ADMIN_ROLE_NAMES` 或用户名落在 `ADMIN_USER_NAMES`。这条要继续保留，但只管平台超管，企业内部的权限判断迁到新的授权层（见第 2 节） |

### 0.1 核对时顺手发现的更大问题：Alembic 目前完全没有真的跑过

用只读查询核对本地开发数据库后确认：

- `alembic_version` 表**不存在**——8 个迁移文件从写下来到现在，从没有被 `alembic upgrade`
  真正执行过一次。当前数据库的实际结构 100% 是 `models/init_db.py` 的
  `Base.metadata.create_all()` + `_run_migrations()`（约 24 条手写幂等 `ALTER TABLE`）
  拼出来的，Alembic 文件只是摆在那里的历史记录，不是真正在起作用的那一套。
- 恰好因为这样，`migrations/versions/20260911_0006_space_permissions.py` 里的
  `op.create_table("organizations", ...)`/`op.create_table("teams", ...)` 从未被执行，
  但对应的 `Organization`/`Team` **ORM 类是真实存在的**，两张表已经通过 `create_all()`
  建好了（本地库确认：都在，都是 0 行）。也就是说现在如果第一次真的对着这个数据库跑
  `alembic upgrade head`，会在这条 `op.create_table` 撞上"表已存在"直接失败——`user_profile`
  等表也是一样的情况，第一个真正会失败的大概是 0002。
- 这就是 Phase 3A 要解决的真实问题，不是走个形式："在全新空库验证 alembic upgrade head
  能够完整建库"这句话现在还做不到，因为 `migrations/env.py` 里 `target_metadata = None`
  （代码注释写着"暂不导入业务模型，避免触发旧 create_all"），`alembic revision
  --autogenerate` 目前根本没法用——这是 Phase 3A 要先修的第一个东西，细节见
  [docs/db-migration-plan.md](db-migration-plan.md)（Phase 3A 单独的执行记录，跟这份
  企业模型设计稿分开，避免两件事混在一份文档里）。

## 1. 数据模型

### 1.1 命名：不新增 Department，也不新建 Organization/Team

```
Organization = 企业（表名 organizations，已存在，单企业部署下长期只会有 1 行）
Team         = 部门（表名 teams，已存在，前端显示"部门"；不出现 department_id）
```

### 1.2 扩展现有表 + 三张新表

三个开放问题已定：**单企业多部门**（复用已存在的 `organizations`，长期只有 1 行；
`teams` 才是真正多行的单位）、角色**新建外键表**（不用字符串枚举）、部门管理员**能看到**
部门下所有知识库空间（见 2.1 节 `get_accessible_space_ids` 第三个来源）。

`organizations`/`teams` 已经存在（[models/init_db.py:367](../models/init_db.py:367)），
现有列是 `id/name/owner_user_id/created_at`（teams 多一个 `organization_id`）——
`owner_user_id` 是隐式创建者，跟 `KnowledgeSpace.user_id` 是 owner、`SpaceMember`
才是显式成员表的既有模式完全一致，不用动；只额外加一个 `status` 列（软停用用，
现有表没有）。**不新建同名概念的表**，新建的只有下面三张：

角色新建一张独立的 `enterprise_role` 表，不是塞进现有的 `Role`
（[models/init_db.py:157](../models/init_db.py:157)）——那张表是平台级角色（决定
`is_admin_user()`），语义和生命周期都不一样，混在一起以后没法单独改企业角色目录。

```python
# --- 对现有两张表的追加（ALTER TABLE ADD COLUMN，纯新增，不改已有列） ---
# organizations.status = Column(String(20), nullable=False, default="active")  # active/disabled
# teams.status         = Column(String(20), nullable=False, default="active")

class EnterpriseRole(Base):
    """企业/部门角色目录。scope 区分用在哪一层，同一层内 code 唯一。

    初始数据（迁移里插入，不是代码里硬编码判断）：
      scope=organization: owner(等级3) / admin(2) / auditor(1) / member(0)
      scope=team:         admin(2) / editor(1) / member(0)
    `rank` 用于"至少要有 X 级"的判断（require_org_role("admin") 实际比较 rank），
    不用在代码里列举所有可能的角色名。
    """
    __tablename__ = "enterprise_role"
    __table_args__ = (
        Index("uq_enterprise_role_scope_code", "scope", "code", unique=True),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(20), nullable=False)   # organization / team
    code = Column(String(30), nullable=False)    # owner / admin / auditor / editor / member
    name = Column(String(60), nullable=False)    # 显示名，如"企业管理员"
    rank = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        Index("uq_org_member", "organization_id", "user_id", unique=True),
        Index("idx_org_member_user", "user_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", name="fk_om_org"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_om_user"), nullable=False)
    role_id = Column(Integer, ForeignKey("enterprise_role.id", name="fk_om_role"), nullable=False)
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
    team_id = Column(Integer, ForeignKey("teams.id", name="fk_tm_team"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id", name="fk_tm_user"), nullable=False)
    role_id = Column(Integer, ForeignKey("enterprise_role.id", name="fk_tm_role"), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
```

（表名用的是已存在的 `organizations`/`teams`，不是 `organization`/`team`——这是 1.1 节
更正之后的实际外键目标，跟前面小节保持一致。）

`role_id` 指向哪个 `scope` 的 `enterprise_role` 由写入时的 service 层校验
（`organization_members.role_id` 必须是 `scope="organization"` 的行），不指望数据库
跨表 CHECK 约束覆盖——MySQL 8（本项目用的版本）虽然支持 CHECK，但不能引用别的表，
这类跨表条件历来都是应用层校验，跟 1.4 节"Team 必须属于同一个 Organization"的校验
放在一起做。

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
teams.organization_id           → 已存在字段（当前是普通 Integer，没有真正的外键约束），
                                   补 ForeignKey("organizations.id")
KnowledgeSpace.organization_id  → 已存在字段，改为在应用层强制非空写入（企业化上线后）
KnowledgeSpace.team_id          → 已存在字段，同上，补 ForeignKey("teams.id")
```

写入时的强制校验：`KnowledgeSpace.team_id` 对应的 `Team.organization_id` 必须等于
`KnowledgeSpace.organization_id`——不允许把一个空间挂到"别的企业的部门"下面。这条校验
放进 service 层（`knowledge_space_service` 的创建/转移入口），不指望数据库约束覆盖跨表条件。

### 1.5 迁移顺序（依赖 Phase 3A 先把 Alembic 权威化做完）

1. `organizations`/`teams` 加 `status` 列（ADD COLUMN，纯新增）；补 `teams.organization_id`
   和 `KnowledgeSpace.team_id`/`organization_id` 的真实外键约束（现有数据都是
   `NULL`/未使用，加约束不会因为脏数据失败——上线前会再跑一次校验确认）。
2. 建 `enterprise_role` / `organization_members` / `team_members` 三张新表，纯新增。
3. 数据回填：为当前部署把 `organizations` 表插入 1 行（"默认企业"，`owner_user_id` 填平台
   管理员），把所有现有用户批量插入 `organization_members`（role=member，平台管理员
   role=owner）——这一步是数据迁移脚本，不是 schema 迁移，要单独写、要能重复执行不出错（幂等）。
4. `KnowledgeSpace.organization_id` 批量回填成默认企业 id（现有数据全部挂到默认企业下，不建
   `Team`、`team_id` 留空——没有部门信息，不能瞎猜）。
5. 上面四步全部落地、跑过一遍全新空库 `alembic upgrade head` 验证后，才开始第 3 节的路由改造。

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
    """给检索/列表接口用：当前用户能看到哪些知识库空间 id，一次查出来，不要在业务代码里
    现算多种来源再拼 OR。三个来源（已定）：
      1. 自己是 KnowledgeSpace.user_id（owner）
      2. 自己在 SpaceMember 里命中（不论角色）
      3. 自己在该空间所属 Team 的 team_members 里 role=admin
         （部门管理员能看到部门下所有知识库空间，即使不是具体空间的 SpaceMember——已确认）
    """
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

## 4. 决策记录

| 问题 | 决策 |
|---|---|
| 要不要做"多企业"数据模型？ | **单企业多部门**：保留 `Organization` 表（结构可扩展），但这次部署下长期只有 1 行；`Team` 是真正的多行单位。`require_org_role` 的"是否属于该企业"这一步照做，不跳过 |
| `role` 用字符串还是外键表？ | **新建**：新增 `enterprise_role` 目录表，`organization_members`/`team_members` 用 `role_id` 外键，不用字符串枚举（见 1.2 节） |
| 部门管理员能不能看到部门下所有空间？ | **能看到**：`get_accessible_space_ids` 第三个来源是"该空间所属 Team 的 team admin"，即使不是具体空间的 `SpaceMember`（见 2.1 节） |

## 5. 下一步

设计、三个开放问题、Phase 3A 这个前置依赖都已经落地。剩下：
1. 把 1.2 节的表结构落成 Alembic 迁移文件 + 1.5 节的数据回填脚本（含幂等性测试）。
2. 授权层（第 2 节）先落地 `require_org_role`/`require_team_role`/`require_space_permission`/
   `get_accessible_space_ids` 四个函数和它们自己的单元测试，再按第 3 节的顺序逐模块接入、
   每接入一个模块跑一遍那个模块的路由级测试确认没有意外放宽或收紧权限。

这两步还没开始——Phase 3A 完成只是解除了阻塞，不代表自动接着做，等你确认再动手。

## 6. 执行结果（第 1 步已落地，2026-09-24）

第 1 步（表结构 + 数据回填）做完了，第 2 步（统一授权层）还没开始。

- `models/init_db.py`：`Organization`/`Team` 加 `status` 列，`teams.organization_id`
  补真实外键；新增 `EnterpriseRole`/`OrganizationMember`/`TeamMember` 三个类；
  `KnowledgeSpace.team_id`/`organization_id` 补真实外键（原来只是普通 `Integer`，
  没有约束）。
- `migrations/versions/20260924_0002_enterprise_rbac_tables.py`：对着独立的空库
  用 autogenerate 生成、验证过跟 Phase 3A 一样的"空库 upgrade head → 再 autogenerate
  → diff 为空"流程，已经应用到本地开发库。`enterprise_role` 的 7 行初始数据
  （organization: owner/admin/auditor/member；team: admin/editor/member）在迁移里
  用 `op.bulk_insert` 种好，不是代码里硬编码判断。
- `scripts/backfill_default_organization.py`：一次性数据回填脚本（`--dry-run`/`--yes`），
  已经在本地开发库跑过：建了 1 个"默认企业"（`owner_user_id` 是当前的平台管理员），
  9 个现有用户全部批号进 `organization_members`（管理员 role=owner，其余 role=member），
  1 个知识库空间的 `organization_id` 回填成默认企业。跑了两遍确认幂等（第二遍 0 新增）。
- `tests/test_backfill_default_organization.py`：真实 DB 集成测试，新建两个测试用户
  验证会被正确回填成 member、重复跑不会插出第二条。
- `tests/_route_client.py` 的 `_purge_users`（路由测试和 E2E 冒烟测试共用的清理函数）
  补了 `organization_members`/`team_members` 两条 DELETE——这两张新表有 `user.id` 外键，
  不先清它们，删测试用户会直接撞 FK 报错。

689 个测试全绿。下一步（第 2 步）：`service/enterprise_access.py` 的
`require_org_role`/`require_team_role`/`require_space_permission`/`get_accessible_space_ids`
四个函数，还没开始写，等确认再动手。
