# Phase 3A：Alembic 权威化——现状核对与执行计划

状态：**核对完成，尚未执行**。这是核对后发现的真实情况，比原计划设想的更严重一点，
写清楚之后再动手，不是走个形式的"生成基线"。

## 1. 核对结论（只读查询，未改动任何东西）

- `alembic_version` 表在本地开发数据库里**不存在**。8 个迁移文件从写下来到现在，
  从没有被 `alembic upgrade` 真正执行过一次。当前数据库的实际结构 100% 来自
  `models/init_db.py` 的 `Base.metadata.create_all()` + `_run_migrations()`
  （约 24 条手写幂等 `ALTER TABLE`，[models/init_db.py:782](../models/init_db.py:782) 起）。
- `migrations/env.py` 里 `target_metadata = None`（注释："暂不导入业务模型，避免触发旧
  create_all"），所以 `alembic revision --autogenerate` 现在完全用不了——这是第一个
  要修的东西。
- 后果已经实际验证到一个具体案例：`20260911_0006_space_permissions.py` 的
  `op.create_table("organizations", ...)`/`op.create_table("teams", ...)` 对应的
  `Organization`/`Team` ORM 类是真实存在的（[models/init_db.py:367](../models/init_db.py:367)），
  两张表已经通过 `create_all()` 建好（本地库确认：都在，都是 0 行）。**如果现在对着
  这个数据库第一次跑 `alembic upgrade head`，会在这条 `op.create_table` 上因为"表已存在"
  直接失败**——往前翻，`0002`（`user_profile` 表，同样已经被 `create_all()` 建好）大概率
  是第一个真正会失败的迁移。
- 结论：现在的 8 个迁移文件是"写了但从没跑过"的历史记录，不是真正在管理数据库的那一套。
  Phase 3A 的目标不是"再加几个迁移文件"，是要让 Alembic 变成从空库到当前状态**真的能走通**
  的唯一权威链条。

## 2. 三种修复思路，需要你选一个

### 方案 A：整条链路重新生成一条"真基线"（推荐）

把 `20260830_0001_baseline.py` 的内容从"pass"换成用 autogenerate 对着一个全新空库
生成的完整 `CREATE TABLE` 语句（覆盖当前所有表，包括 `organizations`/`teams`/
`space_members`/`kb_audit_log` 这些已经存在但从未被迁移真正创建过的表），**同时删除
`0002`～`0008` 这 7 个文件**——它们的改动全部已经包含在重新生成的基线里，留着只会
在空库上重复建表报错。

- 优点：从今天起 `alembic upgrade head` 在全新空库上能一次走通，链条干净，以后
  autogenerate 能正常用来生成增量迁移。
  好处最大：本地库、CI、任何未来的新部署都会走同一条路径。
- 代价：`alembic_version` 从未被任何环境写过（已确认），所以这不是"改写别人已经在用的历史"，
  是"把从来没生效过的历史记录换成真的能用的"——风险比听起来小，但**这是要动的文件最多
  的一种做法**，需要你知情。
- 落地后本地/生产的现有数据库（结构已经是对的，只是没被 Alembic 认领）需要单独
  `alembic stamp head` 一次，把它们标记为"已经在最新版本"，不会重新跑 DDL。

### 方案 B：保留 0001～0008，每个文件补上存在性检查

把 `0002`～`0008` 里的每个 `op.create_table`/`op.add_column` 都包一层"先查是否已存在"
（同 `models/init_db.py` 里 `_run_migrations()` 的老办法），让整条链路在"已经是当前结构
的库"和"全新空库"上都能跑通，不删旧文件。

- 优点：改动范围小，历史记录保持不变。
- 代价：**这正是 Phase 3A 想摆脱的模式**——继续用"查了再改"的防御性写法，而不是让
  Alembic 的版本链条本身就是可信的。以后每加一个迁移都要记得写这层检查，容易漏，
  跟你原计划里"禁止继续使用启动时大量 ALTER TABLE 作为长期迁移方式"的目标是矛盾的。

### 方案 C：不动旧文件，`0009` 开始只管以后

旧的 0001～0008 不管对不对，直接在 `0009` 里 `alembic stamp` 承认现状，之后新迁移
只需要保证在"当前真实结构"上能跑，不要求空库能从 0001 开始重新建库。

- 优点：改动最小，几乎不用碰旧文件。
- 代价：**没有解决 Phase 3A 要解决的问题**——"全新空库能不能用 alembic upgrade head
  完整建库"这条验收标准直接放弃了，CI 里如果要新建一个全新的测试数据库仍然得依赖
  `create_all()`，Alembic 依然不是唯一权威。不推荐，等于把问题往后推。

## 3. 我的建议

选 **方案 A**。理由：`alembic_version` 从来没在任何环境里被写过，"重新生成基线"
不是改写正在依赖的历史，而是把从来没生效过的记录换成真正能用的——这个时间点做，
成本是最低的；再往后推，等到哪天真的有环境已经跑过 `alembic upgrade head` 到某个具体
版本，方案 A 的改写成本会变高很多。

## 4. 方案 A 的具体步骤（评审通过后按顺序做）

1. 修 `migrations/env.py`：`target_metadata = None` 改成从 `models.init_db` 导入
   `Base`，`target_metadata = Base.metadata`。验证：只是让 autogenerate 能"看见"
   模型定义，不会主动连接或改动任何数据库。
2. 在一个全新的、专门用于生成基线的空库上（新建一个独立的 schema，不用本地开发库）
   跑 `alembic revision --autogenerate -m "trusted baseline"`，得到覆盖当前完整
   `Base.metadata` 的 `CREATE TABLE` 语句。
3. 人工过一遍生成的内容：检查有没有 autogenerate 常见的假阳性（比如把 MySQL 默认的
   `utf8mb4` collation 差异也当成变更、`Integer`/`INT` 之类的类型误判），删掉这些噪音。
4. 用这份内容替换 `20260830_0001_baseline.py` 的 `upgrade()`；删除 `0002`～`0008`
   七个文件（内容已经并入新基线）。
5. 验证：在另一个全新空库上跑 `alembic upgrade head`，跑完后用
   `alembic revision --autogenerate` 再生成一次——如果输出是"没有变化"，说明新基线跟
   `Base.metadata`（也就是跟 `create_all()` 今天实际建出来的结构）完全一致。
6. 本地开发库、任何已经用 `create_all()` 建好结构的环境：跑 `alembic stamp head`
   （不执行 DDL，只在该库里创建 `alembic_version` 表并写入当前版本号），让 Alembic
   开始认领这个库。
7. `models/init_db.py` 的 `_create_all_with_retry()`/`_run_migrations()`：改成只在
   `alembic_version` 表不存在时才跑（新环境的第一次兜底），已经被 Alembic 认领的库
   不再走这条路径——彻底停用"启动时大量 ALTER TABLE"这条长期机制，新增字段以后必须
   走新的 Alembic 迁移文件。
8. CI 加一个"全新空库跑 `alembic upgrade head` 后跟当前 `Base.metadata` 做 diff，
   diff 必须为空"的检查（复用第 5 步的验证逻辑），防止以后又出现"改了模型忘了写迁移"
   或反过来的漂移。
9. 生产备份规则和恢复演练——这部分本来就是你 Phase 4 的内容，Phase 3A 只需要在迁移
   执行前"跑一次备份"这一条操作规范上跟 Phase 4 对齐，不重复建一套。

第 1～5 步是纯生成 + 验证，不碰任何真实数据库；第 6 步开始才会在本地开发库和 CI 里
真正执行 `alembic stamp`/未来的迁移。执行前会再跑一次全量单元测试确认没有破坏现有功能。
