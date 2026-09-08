# 自然语言驱动的自定义工作台组件平台

用户用一句话描述想看的内容，AI 把需求解析成**结构化组件配置**（不是前端代码），
统一的运行引擎按配置取数、处理、存快照，前端统一渲染器按 `view.kind` 画成小窗口。

## 组件配置（五段式，spec_version=1）

| 段 | 作用 | P1 白名单 |
| --- | --- | --- |
| `data_source` | 数据从哪来 | `sample` / `catalog`(gold_price,usd_cny,weather) / `system_stats` / `agent_runs` |
| `processor` | 系统怎么处理 | `passthrough` / `normalize_timeseries` / `pick_fields` / `aggregate` / `json_extract` |
| `view` | 怎么展示 | `chart`(line/bar/pie) / `metric` / `markdown` / `table` / `web_monitor` / `task_list` / `system_stats` |
| `trigger` | 多久更新 | `manual` / `hourly` / `daily`(run_at + timezone) |
| `actions` | 用户可操作 | `refresh` / `edit` / `hide` / `delete` |

白名单集中在 `service/widgets/schema.py`（单一事实来源），前端目录接口 `GET /user/widgets`
的 `catalog` 字段即由它导出。

## 接口（全部 async，按当前登录用户隔离）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/user/widgets/design` | 自然语言 → 组件草稿（走用户自己的 `llm_config` 模型；未配置返回中文提示） |
| POST | `/user/widgets` | 按草稿创建（服务端再校验一次，不信任前端回传） |
| GET | `/user/widgets` | 当前用户全部组件 + 能力目录 |
| PATCH | `/user/widgets/{id}` | 改名 / 备注 / 显示隐藏 / 排序 / 整体替换配置 |
| DELETE | `/user/widgets/{id}` | 删除组件及其数据点 |
| POST | `/user/widgets/{id}/run` | 手动运行并保存结果 |
| GET | `/user/widgets/{id}/data` | 最新结果（`with_series=true` 带历史序列） |

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
  processors.py    处理器注册表        process(ctx, raw, config) -> processed
  validator.py     原始 JSON -> 合法 spec / needs_clarification
  designer.py      /design：调用用户模型 + 过 validator
  runner.py        run_widget(widget_id) —— 唯一运行入口
  scheduler.py     到点组件调度入口（P1 预留，WIDGET_SCHEDULER_ENABLED 开关）
```

前端：`src/api/widget.ts` → `src/views/WidgetStudio.vue`（路由 `/widgets`）→
`src/components/widgets/WidgetRenderer.vue` + `registry.ts`（`view.kind -> 组件`，无 if/else 链）。

## 扩展方式（像插件一样加）

- **加数据源**：写一个 `BaseConnector` 子类，`CONNECTORS.add(kind, instance)`，runner 不用改。
- **加处理器**：写一个函数，`@PROCESSORS.register("kind")`，runner 不用改。
- **加展示形态**：写一个组件，在 `registry.ts` 加一行，`WidgetRenderer` 不用改。
- **加触发方式**：构造好 `WidgetRunContext` 后调 `run_widget`，连接器/处理器无感。
- **协议升级**：`schema.SPEC_VERSION` +1，配合 `UserWidget.spec_version` 兼容老组件。

对应扩展点测试见 `tests/test_widget_registries.py`（注册全新 connector+processor 直接驱动 `run_widget`）。

## P1 边界 / P2 计划

P1 的 `catalog` provider 返回**服务端生成的结构真实数据**（不发起外部请求），
保证演示稳定。P2 再做：Worker 自动调度上线、`http`（用户自定义 URL）+ `web_page` +
`knowledge_base` 连接器并统一走 SSRF 防护、`llm_summarize` 处理器、失败退避与数据点保留策略。
