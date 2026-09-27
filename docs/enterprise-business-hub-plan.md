# 企业业务中心（Spring Boot）—— 未来阶段规划

状态：**已确认架构方向，尚未开始实施**。这是 Phase 3D/Phase 4 之后的下一阶段
（暂称 Phase 5），记录设计是为了不丢决策依据，不代表现在就动 Java 代码。
按用户给出的十二步实施顺序，第 1-2 步就是 Phase 3D 阶段2-3（部门权限/数据密级、
中央 Agent 受控路由），本仓库当前所有 Python 代码改动都还在这两步范围内。

## 1. 为什么要新建一个 Spring Boot 服务，而不是都塞进 FastAPI

避免两个极端：把 OA/ERP/CRM 硬塞进现有 AI Agent 平台（业务逻辑和 Agent 逻辑混在一起，
以后谁都不好改）；或者真的去对接/重写四套现成大型软件（工作量不可控）。折中方案：
FastAPI 继续只管"人、权限、Agent、知识库、审计"这些平台能力，新增一个 Java 服务专门
管"请假、采购、客户"这类具体业务单据，两边通过内部网络 + 签名请求通信，各管一段。

## 2. 架构

```
Vue3 企业门户 → Nginx/HTTPS → FastAPI（AI Agent 平台）→[Docker 内部网络，HMAC 签名]→ Spring Boot（企业业务中心）
```

FastAPI 侧新增部门 Agent：HR / 采购 / 销售 / 财务 / IT，中央 Agent 按用户可访问范围
路由到具体部门 Agent；部门 Agent 通过注册好的工具（`get_leave_balance`/
`create_purchase_draft`/`get_customer_summary` 等）调用 Java 服务，不提供任意 SQL/
任意 HTTP 工具。

## 3. 数据归属

同一个 MySQL 实例，两个库两个账号，禁止跨库直接改表：

- `agent_sql`（FastAPI 现有库）：用户/企业/部门/角色、Agent/Prompt/Skill、知识空间
  和向量、会话/记忆/运行轨迹、Agent 操作确认、模型配置和 Token 用量。
- `enterprise_business`（Java 新库）：请假申请和审批记录、产品/库存/部门预算、采购
  申请和采购单、客户/联系人/商机/跟进记录、外部系统调用记录、幂等记录、业务审计。

## 4. Java 侧模块（模块化单体，不拆微服务）

```
enterprise-business-hub/
  common/ security/ organization-client/ idempotency/ audit/
  oa/ procurement/ crm/ sap/ integration/
```

三个业务域先各做最小闭环，第一版明确不做：财务总账、税务、生产制造、供应链全模块。

- **OA 请假**：请假类型/余额 → 草稿 → 提交 → 部门负责人审批（同意/拒绝）→ 状态查询 →
  审批记录。
- **ERP 采购（轻量）**：产品/库存/安全库存 → 判断是否低于安全库存 → 查部门预算 →
  采购申请草稿 → 用户确认 → 部门负责人审批 → 生成采购单 → 更新单据状态。
- **CRM 客户跟进**：客户/联系人/历史跟进 → Agent 生成摘要 → 跟进草稿 → 用户确认 →
  保存跟进记录 → 创建/更新商机（含商机阶段、客户负责人、部门数据隔离）。

## 5. SAP：只定义接口，不自建实现

```java
interface SapConnector {
    Supplier getSupplier(...);
    PurchaseOrder getPurchaseOrder(...);
    PurchaseOrderDraft createPurchaseOrderDraft(...);
    HealthStatus healthCheck();
}
```

演示阶段用 `MockSapConnector`；真实客户提供接口后换 `RealSapConnector`，Agent 端
不用改一行代码。

## 6. 跨服务安全：权限来源只在 FastAPI 一处

Java 不自己判断权限，只验证 FastAPI 签发的短时效上下文：

```json
{
  "user_id": 100, "team_id": 2,
  "scopes": ["procurement.request.create"],
  "operation": "create_purchase_draft",
  "trace_id": "...", "timestamp": 1790000000, "nonce": "..."
}
```

必须具备：HMAC 签名、有效期、`nonce` 防重放、幂等 Key 防重复提交、部门数据过滤、
参数 Schema 校验、写操作用户确认、高风险操作审批、敏感字段脱敏、完整业务审计。

## 7. 审批分两类，不混在一张表里

- **平台审批**（FastAPI 负责）：发布高权限 Skill、修改权限策略、导出限制级数据、
  Agent 执行高风险工具——这是 Phase 3D 阶段4已经规划的 `approval_request`。
- **业务审批**（Java 负责）：请假审批、采购审批、预算审批、客户特殊操作审批——
  这是 Java 服务自己的表，跟上面那张不是同一张。

## 8. 前端新增页面

中央 Agent 工作台、部门 Agent 中心、我的待办、我的申请、OA 请假、库存与采购、
客户与商机、企业操作记录、管理员审批中心、企业集成状态。普通用户只看到自己有权限
的部门模块。

## 9. 实施顺序（用户确认版，本仓库当前进度见括号）

1. 完成 Token 撤销、部门权限和数据密级 —— **= Phase 3D 阶段2**（进行中）
2. 实现中央 Agent 受控路由 —— **= Phase 3D 阶段3**（未开始）
3. 创建 Spring Boot 业务中心和独立数据库 —— 未开始，依赖 1、2
4. 完成 HMAC 认证、幂等、审计和统一异常
5. 完成 OA 请假闭环（先把这一条走完整，再铺采购/CRM，避免三个业务域同时半成品）
6. 完成库存与采购闭环
7. 完成 CRM 客户跟进闭环
8. 将 Java 接口注册成 Agent 工具
9. 完成 SAP Mock Connector
10. 补齐 E2E、越权、重放、重复提交和事务测试
11. Docker Compose 统一部署
12. 压测、监控和备份恢复演练

## 10. 完成标准

中央 Agent 自动路由部门 Agent；不同部门数据不能越权访问；HR Agent 能完成请假申请；
采购 Agent 能根据库存创建采购申请；销售 Agent 能查询客户并记录跟进；写操作必须经过
用户确认；采购等高风险操作必须审批；重复提交不产生重复业务单；Java 服务异常时 AI
平台能明确降级；每次操作能通过 Trace ID 追踪；数据能备份和恢复。

## 11. 决策记录

| 问题 | 决策 |
|---|---|
| 要不要把 OA/ERP/CRM 做成 FastAPI 里的模块？ | **不做**：业务单据逻辑和 Agent/权限平台逻辑分离，新建独立 Java 服务 |
| 要不要拆 OA/采购/CRM 三个微服务？ | **不拆**：一个模块化单体（`enterprise-business-hub`），规模真的起来再拆 |
| Java 服务要不要自己维护一套权限？ | **不维护**：只验证 FastAPI 签发的短时效签名上下文，权限来源始终只有一处 |
| 平台审批和业务审批要不要合并？ | **不合并**：分别属于 FastAPI 和 Java，两张表、两条流程 |
