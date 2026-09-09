# 知识库空间（Knowledge Space）升级总体方案

把当前「Agent 私有知识库」升级为「可复用的企业知识库空间」，Agent 绑定一个或多个空间做
联合检索、带来源引用作答。**基于现有代码扩展，不重写**。

---

## 1. 扩展策略（不是重写）

### 现状

| 能力 | 现在怎么做 |
| --- | --- |
| 知识库归属 | `knowledge` 表 `(user_id, agent_id)`，`agent_id NOT NULL` |
| 向量集合 | ChromaDB 每个 Agent 一个 collection：`agent_{agent_id}_knowledge`（`vector_store_service._get_collection`） |
| 上传 / 入库 | 路由 → `knowledge_service.create_upload_task` → `background_task` 行 → Worker 跑 `rag_service.index_existing_knowledge` |
| 检索 | `rag_service.search(db, user_id, agent_id, query, top_k, knowledge_id)` → `search_similar(agent_id, ...)` |
| 检索入口（异步侧） | `service/rag/search_entry.py::search_scoped`（自带同步 Session + 归属校验，`to_thread` 调用） |
| 归属校验 | `service/access_control.py`（同步 + `*_async` 双版） |
| 评估 | `service/evaluation/rag_eval_service.py`（已有 RAG eval） |

### 核心改造点（只此一处是「硬」的）

**向量集合的键从 `agent_id` 变成 `space_id`。** 其余都是加字段 / 加表 / 加接口。

采用**渐进式 + 双读**，不做一次性全量迁移：

1. `vector_store_service` 参数从 `agent_id:int` 泛化为 `collection_key:str`（`f"space_{space_id}"`）。
   保留旧函数签名做 thin wrapper（`agent_id` → `f"agent_{agent_id}"`），旧调用方不动。
2. 阶段 1 给每个「有知识库文档的 Agent」自动建一个**默认空间**，`knowledge.space_id` 回填，
   并记录 `knowledge_spaces.legacy_agent_id`。
3. 检索时**双读**：先查 `space_{id}` collection，命中不足再查该空间 `legacy_agent_id` 对应的
   `agent_{id}` collection（仅当 `legacy_agent_id` 存在且该空间尚未「迁移完成」）。
4. 新入库一律写 `space_{id}` collection。提供后台任务 `reindex_space`：把某空间下所有
   `legacy` 文档重新切分入库到 `space_{id}` collection，完成后置 `migrated=1`，双读关闭。

好处：上线即可用，旧数据不丢、不阻塞，迁移可按空间粒度分批、可回滚。

---

## 2. 数据库表（新增 / 修改）

> 迁移方式：`models/init_db.py` 加类 + `_run_migrations()` 里加幂等 `ALTER TABLE ... ADD COLUMN`
> （项目现成模式），并写对应 Alembic 版本文件（`migrations/versions/YYYYMMDD_00xx_*.py`）。

### 2.1 新增 `knowledge_spaces`

```
id                BIGINT PK AUTO_INCREMENT
user_id           INT NOT NULL  FK user.id            -- 阶段1：owner
name              VARCHAR(120) NOT NULL
description       VARCHAR(500) NULL
purpose           VARCHAR(60)  NULL                    -- 行业/用途：customer_service / legal / product ...
tags_json         TEXT NULL                            -- ["制度","2024"]
is_enabled        TINYINT NOT NULL DEFAULT 1
status            VARCHAR(20)  NOT NULL DEFAULT 'active'  -- active / archived
-- 统计（异步回填，不实时算）
doc_count         INT NOT NULL DEFAULT 0
chunk_count       INT NOT NULL DEFAULT 0
last_indexed_at   DATETIME NULL
health_score      INT NULL                             -- 0~100，阶段5填
health_json       TEXT NULL                            -- {failed_rate, stale_rate, hit_rate, ...}
-- 迁移/企业预留
legacy_agent_id   INT NULL                             -- 由某 Agent 私有库升级来的
vector_migrated   TINYINT NOT NULL DEFAULT 1           -- 0=还需双读 legacy collection
team_id           INT NULL                             -- 阶段6
organization_id   INT NULL                             -- 阶段6
created_at        DATETIME NOT NULL
updated_at        DATETIME NOT NULL
INDEX (user_id, status), INDEX (team_id), INDEX (organization_id)
```

### 2.2 新增 `agent_knowledge_space`（Agent ↔ 空间，多对多）

```
id                BIGINT PK
agent_id          INT NOT NULL FK agent.id
space_id          BIGINT NOT NULL FK knowledge_spaces.id
created_at        DATETIME NOT NULL
UNIQUE (agent_id, space_id)
INDEX (space_id)
```

### 2.3 修改 `knowledge`（加列，不删旧列）

```
+ space_id        BIGINT NULL  FK knowledge_spaces.id   -- 阶段1回填后逻辑上必填；物理 NULL 兼容存量
+ category        VARCHAR(60) NULL                       -- 文档分类
+ tags_json       TEXT NULL
+ version         VARCHAR(40) NULL                       -- 用户自填版本号
+ source_type     VARCHAR(20) NOT NULL DEFAULT 'upload'  -- upload / web / import
+ source_url      VARCHAR(1000) NULL                     -- web 抓取来源
+ updated_at      DATETIME NULL
INDEX (space_id, is_enabled, status), INDEX (space_id, category)
```
`agent_id` 列**保留**（存量数据、旧检索路径、`vector_store` legacy collection 都还要用）。
新代码以 `space_id` 为准。

### 2.4 修改 `agent`（检索行为配置，加列）

```
+ kb_top_k              INT NOT NULL DEFAULT 5
+ kb_rerank_enabled     TINYINT NOT NULL DEFAULT 0
+ kb_force_citation     TINYINT NOT NULL DEFAULT 1     -- 回答强制带来源
+ kb_refuse_when_empty  TINYINT NOT NULL DEFAULT 1     -- 无命中时拒答
```
现有 `agent.rag_enabled` 保留（总开关）。

### 2.5 新增 `rag_debug_samples`（阶段 4，调试台保存）

```
id                BIGINT PK
user_id           INT NOT NULL
space_id          BIGINT NULL
agent_id          INT NULL
query             TEXT NOT NULL
top_k             INT
rerank_enabled    TINYINT
result_json       TEXT           -- 命中 chunk / score / rerank / context / answer / citations 快照
verdict           VARCHAR(10) NULL  -- useful / useless / null
in_eval_set       TINYINT NOT NULL DEFAULT 0
created_at        DATETIME NOT NULL
INDEX (user_id, created_at), INDEX (space_id)
```

### 2.6 阶段 6 预留（先只出建表脚本，不接线）

`teams`、`organizations`、`space_members(space_id, user_id, role)`、`kb_audit_log`。

---

## 3. 后端模块设计（route → service → dao 分层）

```
FasdtApi/
  knowledge_space.py        新增：Space CRUD + 绑定 + 统计   (prefix /knowledge-spaces)
  knowledge.py              改：上传/列表/检索接收 space_id（agent_id 变可选，二选一）
  rag_debug.py              新增：检索调试 + 保存样例        (prefix /rag-debug)  阶段4
  agent.py                  改：create/update 接收 kb_* 配置 + space 绑定

service/
  knowledge_space/          新增子包（清晰边界）
    __init__.py
    space_service.py        Space CRUD、统计回填、健康分计算
    space_async_service.py  异步读（列表/详情，走 AsyncSession）
    binding_service.py      Agent ↔ Space 绑定校验（含权限）
    membership.py           阶段6 占位：解析「当前用户对 space 的角色」
  rag/
    space_search.py         新增：search_spaces(user_id, space_ids, query, ...) —— 同步入口，
                            自带 Session + 逐个 space 归属校验 + 多集合合并 + rerank + 引用组装。
                            search_entry.search_scoped 重构为它的单-space 特例。
    vector_store_service.py  改：_get_collection 接受 collection_key:str；旧签名保留为 wrapper
    rag_service.py           不动核心；index_existing_knowledge 写向量时用 space collection key

models/
  knowledge_space_dao.py        同步 DAO
  knowledge_space_async_dao.py  异步 DAO（列表/详情/统计）
  agent_knowledge_space_dao.py  绑定表 DAO（同步 + async）
  knowledge_dao.py / knowledge_async_dao.py  加 by_space 查询、space 过滤
  rag_debug_dao.py              阶段4

service/access_control.py
  + get_owned_space(db, user_id, space_id) / get_owned_space_async
  + user_space_ids(db, user_id) —— 当前用户可访问的 space id 集合（阶段1=自己的；阶段6=含团队）
  + assert_agent_spaces_owned(db, user_id, agent_id, space_ids) —— 绑定时校验

service/background_task_service.py（TASK_RUNNERS 注册新任务类型）
  + "reindex_space"      把某 space 的 legacy 文档重切入库到 space collection
  + "recount_space"      重算 doc_count / chunk_count / last_indexed_at
  + "space_health"       阶段5：算健康分
  现有 "upload" / "reindex" / "crawl" runner 改为按 space_id 定位 collection
```

### 检索强化后的返回结构（统一）

```jsonc
{
  "query": "...",
  "space_ids": [12, 15],
  "top_k": 5, "rerank": true,
  "hits": [
    {
      "chunk_id": 991, "content": "...", "score": 0.83, "rerank_score": 0.91,
      "knowledge_id": 44, "chunk_index": 3,
      "source": { "space_id": 12, "space_name": "企业制度知识库",
                  "file_name": "考勤制度_v3.pdf", "file_type": "pdf",
                  "category": "制度", "version": "v3", "source_url": null }
    }
  ],
  "context": "【来源1】...\n【来源2】...",     // 组装给模型的上下文（带编号）
  "citations": [ { "index": 1, "knowledge_id": 44, "file_name": "考勤制度_v3.pdf", "space_id": 12 } ]
}
```

聊天回答里，`chat_service` 把 `citations` 透传到响应；ReAct 的 system prompt 里注入
「引用规则」（force_citation / refuse_when_empty），让模型用 `【来源N】` 标注。

---

## 4. 前端页面设计（面向不懂 RAG 的普通用户）

| 页面 | 路由 | 说明 |
| --- | --- | --- |
| **知识库中心** | `/knowledge-spaces` | 空间卡片网格：名称 / 用途标签 / 文档数 / 片段数 / 最近更新 / 健康状态点 / 启用开关。新建、编辑、删除。 |
| **空间详情** | `/knowledge-spaces/:id` | 顶部统计条 + 文档表（分类/标签/状态/版本/来源筛选）+ 上传区（拖拽多文件、URL 抓取）+ 每行「重建索引 / 启停 / 删除 / 查看片段」。 |
| **知识库调试台** | `/knowledge-spaces/:id/debug`（阶段4） | 左：问题输入 + top_k / rerank 开关。右：分步展示——命中文档、命中片段（带 score / rerank 分）、来源文件、最终上下文（折叠）、模型回答、引用来源。底部「有用 / 无用」+「存为测试样例」。 |
| **Agent 编辑**（改造现有页） | `/agents/:id/edit` | 新增「知识库」区块：多选 Knowledge Space、默认 top_k 滑块、rerank 开关、「回答必须带来源」「查不到就说不知道」两个开关。不动其它字段。 |
| **聊天页**（改造现有 `Chat.vue`） | - | 回答气泡下方展示「参考来源」小标签（文件名，点击可跳空间详情/预览）。 |
| **健康报告**（阶段5） | `/knowledge-spaces/:id/health` | 覆盖率 / 过期率 / 失败率 / 命中率 / 拒答率的可视化 + 「跑一次评估」按钮。 |

前端结构沿用 `frontend/src/{api,views,components}`：
- `api/knowledgeSpace.ts`、`api/ragDebug.ts`
- `views/knowledge/SpaceCenter.vue`、`SpaceDetail.vue`、`RagDebugConsole.vue`、`SpaceHealth.vue`
- `components/knowledge/SpaceCard.vue`、`DocTable.vue`、`UploadDropzone.vue`、`CitationList.vue`、`RagTracePanel.vue`
- 组件拆分参考已做的 `components/widgets/studio/*`

---

## 5. RAG 检索增强设计

1. **多空间联合检索**：`space_search.search_spaces(user_id, space_ids, query, top_k, rerank)`
   - 校验：每个 `space_id` 都在 `user_space_ids(user_id)` 里，否则 `PermissionError`
   - 对每个 space：向量化一次 query（复用）→ 逐 space 查其 collection（`space_{id}`，必要时双读
     `agent_{legacy}`）→ 各取 `max(top_k, 10)` 候选
   - 合并候选，按向量分数排序，截断到检索候选数
   - 反查 `knowledge_chunk` + `knowledge`（带 space / 文件 / 分类 / 版本），过滤 `is_enabled=0` 的文档
   - rerank（若 agent 或调用方开启）→ 截断 `top_k`
   - 组装 `context`（带 `【来源N】` 编号）+ `citations`
2. **拒答策略**：`kb_refuse_when_empty` 开时，命中为空或最高分低于阈值
   （`RAG_MIN_SCORE`，env，默认 0.2）→ 返回空 hits，`chat_service` 让模型输出「资料里没有相关内容」。
3. **强制引用**：`kb_force_citation` 开时，system prompt 追加引用格式要求；回答后做一次轻校验
   （回答含 `【来源` 或 citations 非空），不满足则在响应里标 `citation_missing=true`（不阻断）。
4. **兼容**：Agent 未绑定任何 space 且 `rag_enabled=1` 时，回退到旧 `search_scoped(agent_id)` 路径
   （阶段3 结束前保留），保证现有 Agent 不坏。
5. **性能**：query 向量化只做一次；多 collection 查询用线程池并行（`asyncio.gather` +
   `to_thread`）；rerank 只对合并后的候选做一次。

---

## 6. 权限设计

### 阶段 1（用户级隔离，硬要求）

- 所有 space / 文档 / chunk / 调试接口第一步：`get_owned_space[_async](db, user_id, space_id)`，
  查不到 → `NotFound`（不泄露存在性）。
- 列表接口只查 `WHERE user_id = current_user.id`。
- Agent 绑定 space：`assert_agent_spaces_owned` —— agent 属于当前用户，且每个 space 也属于当前用户。
- 检索：`user_space_ids` 求交集，任何越权 `space_id` 直接 `PermissionError → 403`。
- 复用现有 `service.dependencies.get_current_user[_async]`，不新造鉴权。

### 阶段 6（团队/企业，预留）

- `space_members(space_id, user_id, role)`，role ∈ `owner/admin/editor/viewer`。
- `user_space_ids` 扩展为「自己的 + 作为成员的 + 团队/组织可见的」。
- `membership.resolve_role(user, space) -> role`；写操作按 role 分级（viewer 只读、editor 可传文档、
  admin 可改空间、owner 可删）。
- `kb_audit_log` 记录 space/文档的增删改与绑定变更。
- 管理员视角：`/admin` 下加「企业知识库」列表（复用 `get_current_admin_user_async`）。

阶段 1~5 的所有查询都通过 `user_space_ids` / `get_owned_space` 这两个**唯一入口**做隔离，
阶段 6 只改这两个函数的实现，不改调用点 —— 权限扩展点提前收敛。

---

## 7. 分阶段计划（对齐你的 6 阶段，细化）

| 阶段 | 目标 | 关键产出 | 兼容性 |
| --- | --- | --- | --- |
| **1 ✅** | Space 基础 + 存量升级 | 表 `knowledge_spaces` / `agent_knowledge_space`；`knowledge.space_id` 等列 + `agent.kb_*`；Space CRUD `/knowledge-spaces`；`vector_store` collection key 泛化（`agent_{id}` / `space_{id}`）；`scripts/migrate_agent_kb_to_space.py` 存量迁移（dry-run/`--apply`）；前端「知识库中心」页 + 侧栏入口。 | 旧上传/检索路径完全不变 |
| **2 ✅** | 文档管理增强 | `knowledge.agent_id` 改可空 + `category/tags/version/source_*` 列；`/knowledge-spaces/{id}/documents` 上传/批量/抓取/列表(按分类·标签·状态筛)/改元数据/启停/重建/删除；`rag_service` 向量集合键按 `knowledge.space_id` 解析（`_vector_key`）；入库完成刷新空间统计；**旧 `/knowledge/{agent_id}/*` 上传/抓取内部落到该 Agent 的默认空间**；前端「空间详情」页 | 旧接口保留，行为=写进默认空间 |
| **3 ✅** | 多空间检索 + 引用 | `rag/space_search.search_spaces`（自带 Session + 逐 space 归属校验 + 多集合合并 + rerank + `【来源N】` 组装 + 拒答）；`search_entry.search_for_agent` 统一入口（绑定→多空间，未绑定→旧 `search_scoped`）；`agent.kb_*` + `agent_knowledge_space` 绑定接入 create/update；`agent_runtime` 注入引用/拒答规则 + 透传 `citations`（SSE `citations` 事件）；前端 `AgentCreateDialog` 知识库区块 + `Chat.vue` `CitationList` | 未绑定 space 的 Agent 回退旧 `agent_{id}` 检索路径 |
| **4 ✅** | 知识库调试台 | `/rag-debug/run`（`debug_service.run_retrieval` 经 `to_thread` 跑一次检索快照，`with_answer` 时 `attach_answer` 调 LLM + 启发式忠诚度）；`rag_debug_samples` 表 + `models/rag_debug_dao.py`（异步）；`/rag-debug/samples` 增删改查 + `/samples/export`（评估集 → `rag_eval` cases）；前端 `RagDebugConsole.vue` + `RagTracePanel.vue`，`/knowledge-spaces/:id/debug` | 纯新增 |
| **5 ✅** | 质量与健康分 | `service/knowledge_space/health_service.py`（只读 DB 算文档侧 failed/pending/stale/empty_done + 检索侧 hit/refuse/citation/useful 率 → 加权 `health_score` 0~100）；`GET /knowledge-spaces/{id}/health` 实时算并回写 `health_*`；`space_health` 后台任务 runner；`rag_eval_service.run_for_space` + `POST /evaluation/space/{id}/rag`（检索走 `space_search`）；前端 `SpaceHealth.vue`；Widget `knowledge_space` connector（`schema` 白名单 + `designer` 提示，注册即用） | 纯新增 |
| **6 ✅** | 企业权限落地 | `space_members` / `kb_audit_log` 建表 + 接线（`teams` / `organizations` 建表预留，暂不参与可见性）；`access_control.get_owned_space[_async]` / `user_space_ids[_async]` 扩成「owner 或任意角色成员」；`get_space_role[_async]` + `membership.can_*` 做写权限分级（viewer 只读 / editor 增删文档 / admin 改空间·管成员 / owner 删空间）；`space_async_service` + `document_service` 写操作加 role 校验 + `kb_audit_dao` 审计；`/knowledge-spaces/{id}/members`、`/{id}/audit` 路由；`/admin/knowledge-spaces` 企业视角；前端 `SpaceMembersPanel` + `AdminKnowledgeSpaces.vue` | `user_id` owner 语义保留为 role=owner，调用点不变，只改两个隔离入口实现 |

---

## 8. 每阶段改哪些文件

### 阶段 1
- `models/init_db.py`：+ `KnowledgeSpace` / `AgentKnowledgeSpace` 类；`_run_migrations()` 加
  `knowledge` / `agent` 的 `ADD COLUMN`
- `migrations/versions/<new>_knowledge_spaces.py`
- `models/knowledge_space_dao.py`（新）、`models/knowledge_space_async_dao.py`（新）、
  `models/agent_knowledge_space_dao.py`（新）
- `service/knowledge_space/space_service.py`、`space_async_service.py`、`binding_service.py`（新）
- `service/access_control.py`：+ `get_owned_space[_async]` / `user_space_ids`
- `service/rag/vector_store_service.py`：`_get_collection(collection_key)` + 旧签名 wrapper；
  `add_vectors` / `search_similar` / `delete_vectors_by_knowledge` / `delete_collection` 同步改
- `FasdtApi/knowledge_space.py`（新）；`FasdtApi/main.py` 注册路由
- `scripts/migrate_agent_kb_to_space.py`（新，一次性存量迁移：建默认空间 + 回填 `space_id` +
  `legacy_agent_id` + `vector_migrated=0`）；或做成 `bootstrap_database` 里的幂等步骤
- 前端：`api/knowledgeSpace.ts`、`views/knowledge/SpaceCenter.vue`、`components/knowledge/SpaceCard.vue`、
  `router/index.ts` 加路由、`AppShell` 加入口
- `tests/test_knowledge_space_service.py`、`tests/test_routes_isolation.py`（加 space 跨用户 404）
- `scripts/release_check.py`：`REQUIRED_FILES` 加新模块；`docs/` 更新
- `docs/backend-map.md`（+ 4c 知识库空间节）、`docs/knowledge-space-plan.md`（本文件，标进度）

### 阶段 2
- `models/knowledge_dao.py` / `knowledge_async_dao.py`：`list_by_space` / space 过滤 / tag/category 更新
- `service/knowledge_service.py` / `knowledge_async_service.py`：`create_upload_task` 等接 `space_id`；
  `set_document_enabled` / `create_reindex_task` / `delete_document_completely` 改按 space 定位
- `service/background_task_service.py`：注册 `reindex_space` / `recount_space` runner
- `FasdtApi/knowledge.py`：上传/批量/抓取/列表接口签名（`space_id` 优先，`agent_id` 兼容）
- 前端：`views/knowledge/SpaceDetail.vue`、`components/knowledge/{DocTable,UploadDropzone}.vue`
- `tests/test_knowledge_service.py`（扩）、`tests/test_widget_p2_connectors.py` 不动
- `docs` + `release_check`

### 阶段 3
- `service/rag/space_search.py`（新）；`service/rag/search_entry.py` 重构为其单-space 特例
- `models/agent_knowledge_space_dao.py`：`list_space_ids_by_agent`
- `service/agent_service.py` / `agent_async_service.py`：create/update 落 `kb_*` + 绑定
- `FasdtApi/agent.py`：`AgentCreate` / `AgentUpdate` 加 `space_ids` / `kb_top_k` / `kb_rerank` /
  `kb_force_citation` / `kb_refuse_when_empty`
- `service/chat_service.py` + `service/runtime/agent_runtime.py`：`_compose_system_prompt` 注入引用/
  拒答规则；检索改调 `space_search`；结果里带 `citations` 并透传
- 前端：`views/agents/AgentEdit.vue`（现有页加区块）、`Chat.vue`（`CitationList.vue`）、
  `components/knowledge/CitationList.vue`
- `tests/test_rag_space_search.py`、`tests/test_routes_isolation.py`（检索越权 403）
- `docs` + `release_check`

### 阶段 4
- `models/rag_debug_dao.py`（新）；`models/init_db.py` + `RagDebugSample`；migration
- `service/rag/debug_service.py`（新）：跑一次完整检索 + 可选 LLM，产出快照
- `FasdtApi/rag_debug.py`（新）；`main.py` 注册
- 前端：`api/ragDebug.ts`、`views/knowledge/RagDebugConsole.vue`、`components/knowledge/RagTracePanel.vue`
- `tests/test_rag_debug_service.py`
- `docs` + `release_check`

### 阶段 5
- `service/knowledge_space/health_service.py`（新）
- `service/evaluation/rag_eval_service.py`：+ `run_for_space(space_id, ...)`
- `service/background_task_service.py`：`space_health` runner
- `service/widgets/connectors/knowledge_space.py`（新 connector）+ `schema.py` 白名单 + `designer.py` 提示
- 前端：`views/knowledge/SpaceHealth.vue`；Widget Studio 无需改（connector 注册即用）
- `tests/test_space_health_service.py`、`tests/test_widget_*`（connector）
- `docs` + `release_check`

### 阶段 6
- `models/init_db.py`：`Team` / `Organization` / `SpaceMember` / `KbAuditLog`；migration
- `models/space_member_dao.py`、`models/kb_audit_dao.py`（+ async）
- `service/knowledge_space/membership.py`：`resolve_role` 实现；`access_control.user_space_ids` 扩展
- 各 space 写操作加 role 校验 + audit 记录（**只在 service 层，不散到路由**）
- `FasdtApi/admin.py`：企业知识库视图
- 前端：空间成员管理 UI、审计日志页
- `tests/test_space_permission.py`
- `docs` + `release_check`

---

## 9. 每阶段验收标准

**阶段 1**
- `POST/GET/PATCH/DELETE /knowledge-spaces` 正常；`GET` 列表只返回自己的空间。
- 用别人的 `space_id` 访问任意 space 接口 → 404（`tests/test_routes_isolation.py` 覆盖）。
- 存量迁移后：每个原有知识库文档都有 `space_id`；对应 space `legacy_agent_id` 正确、`vector_migrated=0`。
- **原 `/knowledge/{agent_id}/*` 上传与 `/knowledge/{agent_id}/search` 行为不变**（回归测试通过）。
- `python -m unittest` 全绿；`npm run build` 通过；`npm run release:check` 通过。

**阶段 2**
- 一个用户能在多个空间里分别管理文档；文档列表可按 category / tag / status 过滤。
- 上传 / URL 抓取都能落到指定 `space_id`，Worker 入库后 chunk 进 `space_{id}` collection。
- 文档「重建索引」「启停」「删除」在 space 维度可用；错误信息可见。
- `recount_space` 后 `doc_count` / `chunk_count` 与实际一致。

**阶段 3** ✅
- Agent 可绑定 ≥2 个 space；检索命中来自多个空间，结果含 `source.file_name` / `space_name` / `score`。
  → `space_search.search_spaces` 逐 space 查 `space_{id}` collection（`vector_migrated=0` 双读 `agent_{legacy}`），
  合并后按分数排序、反查 `knowledge` 元数据、过滤禁用文档。
- 开 `kb_force_citation` 时回答带 `【来源N】`；关时不强制。→ `agent_runtime._compose_kb_prompt` 注入引用规则。
- 开 `kb_refuse_when_empty` 且无命中 / 最高分 < `RAG_MIN_SCORE`(env,默认0.2) 时，
  prompt 指示模型输出「知识库中没有相关内容」而非编造。→ `space_search._should_refuse`。
- 用户绑定未授权 space → 400（`agent_service._validate_space_ids` 走 `access_control.user_space_ids`）；
  检索传未授权 `space_ids` → `search_spaces` 抛 `PermissionError`。
- 未绑定 space 的旧 Agent 聊天走 `search_entry.search_for_agent` 的 `mode="agent"` 回退分支，行为不变。
- 测试：`tests/test_rag_space_search.py`（候选数/拒答阈值/`【来源N】`组装/rerank 纯逻辑）；
  `tests/test_routes_isolation.py::test_agent_space_binding_and_cross_user_reject`（绑定 + 越权 400）。

**阶段 4** ✅
- `POST /rag-debug/run` 返回 query / mode / 命中 chunk（含 score、rerank_score、source）/ 最终 context /
  citations / refused；`with_answer=1` 时附带 LLM 回答 + 启发式忠诚度（`evaluate_faithfulness`）。
- `POST /rag-debug/samples` 存快照 → `GET /rag-debug/samples`（可按 space / 评估集筛）→
  `PATCH`（`verdict` useful/useless、`in_eval_set`）→ `GET /samples/export` 产出 `rag_eval` 的 cases
  （`expected_knowledge_ids` / `expected_chunk_ids` 从快照 hits 反推，useless 样例期望「查不到」）。
- 越权：`run` 传别人的 `space_ids` → `space_search` 抛 `PermissionError` → 403；
  `samples` 列表/导出传别人的 `space_id` → 404；改/删别人的样例 → 404。
- 测试：`tests/test_rag_debug_service.py`（hit 归一化 / 样例序列化 / 导出用例 / 入参校验）；
  `tests/test_routes_isolation.py::test_rag_debug_console_isolation`。

**阶段 5** ✅
- 每个 space 有 `health_score`（0~100）与明细：文档侧 total/enabled/done/failed/pending/stale/empty_done
  + 各比率；检索侧（≥3 条调试样例时纳入评分）hit_rate/refuse_rate/citation_rate/useful_rate。
  `GET /knowledge-spaces/{id}/health` 实时算并回写 `knowledge_spaces.health_score` / `health_json`；
  `space_health` 后台任务可批量刷。空空间给中性 60，其余从 100 起按「失败>未入库>过期>空切片>低命中」扣分。
- `POST /evaluation/space/{space_id}/rag`（`rag_eval_service.run_for_space`）：检索走
  `space_search.search_spaces`（多空间联合），逐条 `to_thread`，复用 `evaluate_retrieval_case` +
  `_summarize_case_reports`，产出命中率/召回/precision@k/mrr/忠诚度。
- Widget `knowledge_space` connector：`config.space_id`，经 `to_thread(health_snapshot)` 出健康分
  summary + rows，`schema.CONNECTOR_KINDS`/`CONNECTOR_LABELS` 已加、`designer` 提示已加。
- 越权：`health` / `evaluation/space` 传别人的空间 → 404；connector 非本人空间 → `PermissionDenied`。
- 测试：`tests/test_space_health_service.py`（评分 / 比率 / 阈值 / connector 注册）；
  `tests/test_routes_isolation.py::test_space_health_and_eval_isolation`。

**阶段 6** ✅
- viewer 不能上传 / 改 / 删（`document_service._require_write` → `can_write_doc` → 403）；
  editor 能传文档不能改空间（`space_async_service.update_space` → `can_manage_space` → 403）；
  admin 能改空间、管成员不能删空间（`can_delete_space` 仅 owner）；owner 全权。
- 非成员访问共享 space → 404（`get_owned_space[_async]` 查不到 owner 也查不到 space_members 角色）。
  说明：越权统一返回 404（不泄露存在性），有读权限但无写权限的成员写操作返回 403。
- 空间设置 / 文档增删改 / 成员变更 在 `kb_audit_log` 有记录（`kb_audit_dao.record[_async]`，best-effort）。
- 管理员 `GET /admin/knowledge-spaces` 看到平台所有 space（owner / 规模 / 成员数 / 健康分）；普通用户 403。
- `access_control` 只改了 `get_owned_space` / `user_space_ids` / 新增 `get_space_role` 三个函数，
  阶段 1~5 的调用点一行没动（隔离扩展点提前收敛）。
- 测试：`tests/test_space_permission.py`（角色解析 / 能力判定 / rank）；
  `tests/test_routes_isolation.py::test_space_membership_roles_and_audit`（viewer→editor→admin 分级 +
  审计 + 管理员视角 + 非成员 404）。

## 附：企业权限的收敛点

`access_control` 里知识库空间相关的隔离全部集中在三个函数：

| 函数 | 语义 | 谁在用 |
| --- | --- | --- |
| `get_owned_space[_async](db, uid, sid)` | 「能读到这个空间吗」→ owner 或任意角色成员，否则 None | 所有 space / 文档 / 调试 / 健康 读路径的 404 门槛 |
| `user_space_ids[_async](db, uid)` | 可访问的 space id 集合（owned ∪ member） | 多空间检索、Agent 绑定校验、调试样例范围 |
| `get_space_role[_async](db, uid, sid)` | owner / admin / editor / viewer / None | service 层写操作 + `membership.can_*` 做 403 分级 |

`teams` / `organizations` 表已建，后续要接「团队成员自动可见团队 space」只需在这三个函数里加一段
（加 `team_members` 表 + union），路由和 service 调用点仍然不用动。

---

## 10. 风险与注意事项

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| **向量集合迁移** | Chroma 无 rename；`agent_{id}` → `space_{id}` 需重灌或双读 | 双读 + 按 space 的 `reindex_space` 后台任务分批迁；`vector_migrated` 标位控制；迁移失败可重跑 |
| **存量数据回填** | `knowledge.space_id` 回填出错会让存量文档「消失」 | 迁移脚本幂等 + dry-run 模式先打印计划；回填只加不删；`agent_id` 列保留做兜底查询 |
| **多集合检索性能** | 绑定 N 个 space 时 N 次向量查询 + 一次 rerank | query 向量化只一次；N 次查询 `asyncio.gather(to_thread)` 并行；`top_k` 上限（如 ≤20）；rerank 仅对合并候选 |
| **同步/异步边界** | RAG 链路仍是同步（见 `docs/sync-async-boundary.md`） | 新的 `space_search` 沿用 `search_entry` 的模式：同步入口自带 Session，路由 `await asyncio.to_thread(...)`；不把同步 Session 带进路由 |
| **权限扩展点分散** | 阶段 6 加团队权限时改动面失控 | 阶段 1 起，所有隔离只走 `user_space_ids` / `get_owned_space` 两个入口；阶段 6 只改实现 |
| **破坏现有 Agent 私有库** | 用户可能已有大量 Agent 私有知识库在用 | 旧接口全部保留并内部映射到「默认空间」；阶段 3 前不强制迁移；回归测试守住旧路径 |
| **拒答误伤** | 分数阈值设太高导致有资料也拒答 | 阈值走 env 可调；调试台（阶段 4）让用户自己看分数校准；默认阈值保守（0.2） |
| **引用校验** | 强校验会误判（模型换了引用写法） | 只做「软标记」`citation_missing`，不阻断回答 |
| **迁移与 Alembic 过渡期** | 项目现在模型定义未拆分，Alembic 未全量接管 | 沿用现有「`_run_migrations()` 幂等 ALTER + 手写 Alembic 版本」双写模式，和现状一致 |
| **前端复杂度** | 调试台信息密集，普通用户看不懂 | 默认折叠技术细节（context、vector_id），只显「命中了哪些文件、答得对不对」；技术面板可展开 |
| **Widget connector 复用** | 阶段 5 的知识库健康 connector 要按 `ctx.user_id` 隔离 | 参考现有 `knowledge_base` connector：经 `to_thread` 调同步入口，入口内校验 space 归属 |

---

## 附：与旧「资料库 / 个人资料」页面的收敛

历史上「知识库」在 UI 里叫「资料库 / 个人资料 / 我的资料空间」，且旧页
（`/knowledge/:agentId`，`views/Knowledge.vue`）自带一个「我的资料空间」——按 Agent 复制文档，
这与新的 Knowledge Space 概念重复。收敛策略（不删后端能力）：

| 位置 | 处理 |
| --- | --- |
| 术语 | 统一叫「知识库」；「资料」只用于指单份文档 |
| 侧栏「个人资料」 | 改名「本助手知识库」，`active` 仅匹配 `/knowledge/`（不再和知识库中心抢高亮） |
| `Knowledge.vue` 标题 | 「资料库管理」→「本助手知识库」，加一行跳「知识库中心」的链接 |
| `Knowledge.vue` 的「我的资料空间」面板 | 改名「从其他助手复制资料（旧方式）」，提示改用知识库中心建独立库供多助手共用。功能保留，视觉降级 |
| 后端 | `/knowledge/{agent_id}/*`、`import_existing_document` 等**全部保留**（阶段2 内部映射到默认空间；阶段3 由「Agent 绑定空间」取代复制） |

阶段 2 起，文档管理主入口迁到「知识库中心 → 空间详情」；`Knowledge.vue` 逐步瘦身为
「本助手绑定了哪些知识库 + 快速检索测试」，最终可下线。

## 附：不做清单（遵照要求）

- 不动 ReAct 执行核心（`react_engine` / `ToolExecutor`），只在 `_compose_system_prompt` 注入规则、
  在结果层加 citations。
- 不重写 `rag_service` / `embedding_service` / rerank，只加 `space_search` 编排层和 collection key 泛化。
- 不删 `knowledge.agent_id` 及旧 `/knowledge/{agent_id}/*` 接口。
- 不在路由里写检索 / 组装 / 权限逻辑，全部下沉 service。
- 密钥仍走用户 `llm_config`；测试用 `tests/_route_client.py` 的临时用户，不硬编码账号。
