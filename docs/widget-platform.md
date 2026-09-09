# 自然语言驱动的自定义工作台组件平台

用户用一句话描述想看的内容，AI 把需求解析成**结构化组件配置**（不是前端代码），
统一的运行引擎按配置取数、处理、存快照，前端统一渲染器按 `view.kind` 画成小窗口。

## 组件配置（五段式，spec_version=1）

| 段 | 作用 | 白名单 |
| --- | --- | --- |
| `data_source` | 数据从哪来 | `sample` / `catalog`(gold_price,usd_cny,weather) / `system_stats` / `agent_runs` / **`http`** / **`web_page`** / **`knowledge_base`** / **`knowledge_space`** |
| `processor` | 系统怎么处理 | `passthrough` / `normalize_timeseries` / `pick_fields` / `aggregate` / `json_extract` / **`llm_summarize`** |
| `view` | 怎么展示 | `chart`(line/bar/pie) / `metric` / `markdown` / `table` / `web_monitor` / `task_list` / `system_stats` |
| `trigger` | 多久更新 | `manual` / `hourly` / `daily`(run_at + timezone) |
| `actions` | 用户可操作 | `refresh` / `edit` / `hide` / `delete` |

**P2 数据源 / 处理器的 config：**

| kind | 必填 config | 可选 config |
| --- | --- | --- |
| `http` | `url`(http/https) | `method`(GET/POST) `headers` `body` `as`(json/text) `json_path` |
| `web_page` | `url` | `mode`(text / monitor) `max_chars` |
| `knowledge_base` | `agent_id` `query` | `top_k`(1~10) |
| `knowledge_space` | `space_id` | —（输出某知识库空间的健康分 + 文档/检索质量指标，经 `to_thread` 调 `health_service.health_snapshot`，按 `ctx.user_id` 校验空间归属） |
| `llm_summarize` | - | `instruction` `style`(brief/report/one_line) `max_chars`（配合 `view.kind=markdown`；输出有结构的中文 Markdown：结论加粗 + 带数字的要点 + `> 提醒`；剥掉寒暄/代码围栏；无可用模型时优雅降级不报错） |
| `threshold_alert` | 阈值 | 简写 `{"gt":100}` / `{"lt":5}` 或 `rules=[{"level":"warn\|alert","op":"gt\|lt\|gte\|lte\|eq","value":N,"message":"…"}]`；`field` 指定比较字段。产出 `level`(ok/warn/alert)+提醒文案，`level!=ok` 时该组件在列表接口被标 `attention` |

白名单集中在 `service/widgets/schema.py`（单一事实来源），前端目录接口 `GET /user/widgets`
的 `catalog` 字段即由它导出。

## 接口（全部 async，按当前登录用户隔离）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/user/widgets/design` | 自然语言 → 组件草稿（走用户自己的 `llm_config` 模型；未配置返回中文提示） |
| POST | `/user/widgets/preview` | 按草稿**真实跑一次**取数/处理，但不落库 —— 创建前先看效果 |
| POST | `/user/widgets` | 按草稿创建（服务端再校验一次，不信任前端回传） |
| GET | `/user/widgets` | 当前用户全部组件 + 能力目录 |
| PATCH | `/user/widgets/{id}` | 改名 / 备注 / 显示隐藏 / 排序 / 整体替换配置 |
| DELETE | `/user/widgets/{id}` | 删除组件及其数据点 |
| POST | `/user/widgets/{id}/run` | 手动运行并保存结果 |
| GET | `/user/widgets/{id}/data` | 最新结果（`with_series=true` 带历史序列，前端「详情/历史」用） |
| GET | `/user/widgets/{id}/export` | 导出组件配置（只含 spec，可分享） |
| POST | `/user/widgets/import` | `{payload}` 里带导出 JSON → 照常校验后新建 |

## 展示层增强

- **auto_view（自动升级图表）**：运行引擎在结果其实是「按时间排列的一列数值」（折线）或
  「几个类目各一个数值」（柱状）、但用户选的是文字/表格类视图时，`service/widgets/shape.py`
  的 `detect_series` / `detect_categorical` 会算出一个图表建议塞进 `payload.auto_view`
  （含归一后的 `points`）。前端 `WidgetRenderer` 默认渲染 auto_view，并给「图 / 原始」切换。
  `chart` / `metric` 等本身是图的视图不加。
- **时间戳**：`payload.generated_at` + `llm_summarize` / `threshold_alert` 产出里的时间；
  `MarkdownWidget` 顶部展示「生成时间 · 来源」。
- **需关注标记**：列表接口给每个组件算 `attention`（`alert` / `warn` 来自 threshold_alert，
  `changed` 来自 web_page monitor）。前端卡片加色点 + 边框，可按「需关注」筛选、优先排序。
- **详情/历史**：`WidgetStudio` 卡片「详情」按钮弹窗 —— 四句话说明 + 上次/下次运行 +
  当前内容 + 近 N 次运行表（时间 / 成功失败 / 结果）。
- **试运行 / 导出导入 / 拖拽排序**：创建前 `POST /preview` 看真实效果；卡片可导出 JSON 分享、
  从 JSON 导入；卡片支持拖拽调整顺序（落地即 `PATCH sort_order`）。

## 分层

```
FasdtApi/user_widget.py              route
service/widget_async_service.py      编排
models/user_widget_async_dao.py      dao（user_widgets / widget_data_points）
service/widgets/
  schema.py        白名单 + 中文文案 + describe_spec()
  context.py       WidgetRunContext（user_id/widget_id/now/db/request_id/trigger）
  registry.py      通用注册表
  connectors/      数据源连接器注册表  fetch(ctx, config) -> raw_data
                   （P2：http / web_page / knowledge_base，外呼统一过 SSRF 校验 + 重试/熔断）
  processors.py    处理器注册表        process(ctx, raw, config) -> processed（P2：llm_summarize / threshold_alert）
  validator.py     原始 JSON -> 合法 spec / needs_clarification
  designer.py      /design：调用用户模型 + 过 validator
  runner.py        run_widget(widget_id) —— 唯一运行入口（含失败退避 + 数据点保留 + auto_view）
                   run_spec_preview(spec) —— 创建前试运行，不落库
  retention.py     数据点保留策略（纯函数：条数上限 / 失败限额 / 过期清理 / 永远留最新+最新成功）
  shape.py         数据形态识别（纯函数：时间序列 -> 折线图 / 类目 -> 柱状图 auto_view 建议）
  scheduler.py     到点组件调度：逐个乐观锁抢占 + 单独提交，默认开启
```

前端：`src/api/widget.ts` → `src/views/WidgetStudio.vue`（路由 `/widgets`）→
`src/components/widgets/WidgetRenderer.vue` + `registry.ts`（`view.kind -> 组件`，无 if/else 链）。

## 同步 / 异步边界

`service/widgets/**` 保持 **100% 异步**：runner、scheduler、所有 connector.fetch / processor
都是 `async`，只接受 `AsyncSession`（`ctx.db`）。不得出现 `SessionLocal(` / `get_db` /
同步 `requests`（`tests/test_widget_sync_boundary.py` 守卫）。

跨到同步子系统只有一种方式——`asyncio.to_thread` 调它们的**单一同步入口**：

| 子系统 | 入口 | 说明 |
| --- | --- | --- |
| RAG 检索 | `service.rag.search_entry.search_scoped(user_id, agent_id, query, top_k, knowledge_id=None)` | 自带同步 Session + 归属校验；ChromaDB / rerank 仍是同步。组件用 `search_for_widget` 薄封装 |
| 网页抓取 | `service.web_crawler_service.crawl_url_to_markdown(url)` | requests + 重定向逐跳校验 + 大小限制；`validate_crawl_url` 的阻塞 DNS 也走 to_thread |

外呼 HTTP（`http` 连接器）已是 httpx 原生（`service.http_resilience.async_request_with_retry`）。
后台 Worker 用一个进程内常驻事件循环跑组件调度 tick，不再每轮 `asyncio.run()` 建/拆 loop。

RAG / 爬虫子系统本身的 async 化是独立课题，不在本平台范围内。

## 扩展方式（像插件一样加）

- **加数据源**：写一个 `BaseConnector` 子类，`CONNECTORS.add(kind, instance)`，runner 不用改。
- **加处理器**：写一个函数，`@PROCESSORS.register("kind")`，runner 不用改。
- **加展示形态**：写一个组件，在 `registry.ts` 加一行，`WidgetRenderer` 不用改。
- **加触发方式**：构造好 `WidgetRunContext` 后调 `run_widget`，连接器/处理器无感。
- **协议升级**：`schema.SPEC_VERSION` +1，配合 `UserWidget.spec_version` 兼容老组件。

对应扩展点测试见 `tests/test_widget_registries.py`（注册全新 connector+processor 直接驱动 `run_widget`）。

## 自动调度（P2 已上线）

后台 Worker 每 `WIDGET_SCHEDULER_POLL_SECONDS`（默认 60s）跑一轮 `run_due_widgets`：
取 `enabled=1 且 next_run_at<=now` 的组件，逐个用乐观锁抢占（把 `next_run_at` 推到一个
租约时间，只有 `UPDATE ... WHERE next_run_at=<原值>` 命中的进程真正执行），跑完由 runner
覆盖成真正的下次运行时间。多 Worker 安全；进程在租约期内崩了，租约到期后自动被重新捡起。

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `WIDGET_SCHEDULER_ENABLED` | `1` | 设 `0/false` 关闭自动调度 |
| `WIDGET_SCHEDULER_POLL_SECONDS` | `60` | 调度轮询间隔 |
| `WIDGET_SCHEDULER_LEASE_MINUTES` | `10` | 抢占租约时长 |
| `WIDGET_SCHEDULER_MAX_PER_TICK` | `50` | 每轮最多处理多少个组件 |

## 失败退避与数据保留（P2）

- **退避**：定时组件失败后，`next_run_at` 改为指数退避（`WIDGET_RETRY_BACKOFF_BASE_MINUTES`×2ⁿ，
  上限 `WIDGET_RETRY_BACKOFF_CAP_MINUTES`）；连续失败达到 `WIDGET_MAX_CONSECUTIVE_FAILS`（默认 6）
  次后 `last_status="paused"`、停止自动调度，用户手动运行成功即恢复。
- **保留**：每次运行后按 `service/widgets/retention.py` 裁剪数据点——最近 `WIDGET_KEEP_POINTS`（200）
  条、失败点单独限额 `WIDGET_KEEP_ERROR_POINTS`（20）条、超过 `WIDGET_KEEP_DAYS`（90）天清理，
  但永远保留「最新一条」和「最新一条成功」。

## 仍未做

- `catalog` provider 仍返回服务端合成数据（不外呼）；接真实第三方数据以同样的 provider 接口接入。
- 触发方式尚无 `event` / `webhook` / `cron`。
- 分析类处理器只做了 `llm_summarize` / `threshold_alert`；`trend_analysis` / `classification`
  / `ranking` 待做。
- `attention` 目前只在页面上提示，没有站内/邮件/webhook 推送。
