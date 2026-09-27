"""采购 Agent 工具（Phase 5，docs/enterprise-business-hub-plan.md 第4/7节）。

跟 `service/tools/oa_leave.py` 是同一种薄工具层：签名转发到企业业务中心的
`com.enterprisehub.procurement.ProcurementController`，业务规则（预算够不够、
状态机对不对）全在 Java 那边判断。采购比请假多一条硬约束：所有操作都要
`team_id`（没有部门就不知道该查哪个部门的预算），当前用户不在任何部门时
直接返回错误 JSON，不硬凑一个默认值。
"""
import json
import uuid
from typing import Optional

from service import enterprise_hub_client as hub
from service.tools.base import BaseTool, ToolRegistry


def _resolve_team_id(user_id: int) -> Optional[int]:
    from models.init_db import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT team_id FROM team_members WHERE user_id=:u AND status='active' ORDER BY id LIMIT 1"),
            {"u": user_id},
        ).first()
        return row[0] if row else None
    finally:
        db.close()


def _require_user_and_team(ctx) -> tuple:
    if not ctx or not ctx.user_id:
        raise ValueError("缺少用户上下文，无法调用企业业务中心")
    user_id = ctx.user_id
    team_id = _resolve_team_id(user_id)
    if team_id is None:
        raise ValueError("当前用户不属于任何部门，无法进行采购操作（采购按部门查库存和预算）")
    return user_id, team_id


def _error_json(exc: hub.EnterpriseHubError) -> str:
    return json.dumps({"error": exc.detail, "status_code": exc.status_code}, ensure_ascii=False)


@ToolRegistry.register
class GetInventoryStatusTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "get_inventory_status"

    def get_description(self) -> str:
        return "查询某个产品（按 SKU）的库存量和是否低于安全库存。用户问库存够不够、要不要补货时调用。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"sku": {"type": "string", "description": "产品编号"}},
            "required": ["sku"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        sku = kwargs.get("sku")
        try:
            result = hub.call(
                "GET", f"/procurement/products/{sku}", user_id, team_id,
                ["procurement.read"], "get_inventory_status",
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class GetDepartmentBudgetTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "get_department_budget"

    def get_description(self) -> str:
        return "查询当前用户所在部门某年度的采购预算余额。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"year": {"type": "integer", "description": "查询年度，不填默认当前年"}},
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        year = kwargs.get("year")
        path = "/procurement/budget" + (f"?year={int(year)}" if year else "")
        try:
            result = hub.call("GET", path, user_id, team_id, ["procurement.read"], "get_department_budget")
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class CreatePurchaseDraftTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "create_purchase_draft"

    def get_description(self) -> str:
        return "创建一条采购申请草稿（还没提交），可以包含多个产品明细。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "description": "采购明细列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string", "description": "产品编号"},
                            "quantity": {"type": "integer", "description": "采购数量"},
                        },
                        "required": ["sku", "quantity"],
                    },
                },
            },
            "required": ["lines"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        lines = kwargs.get("lines") or []
        try:
            result = hub.call(
                "POST", "/procurement/requests", user_id, team_id, ["procurement.write"], "create_purchase_draft",
                json_body={"lines": lines}, idempotency_key=str(uuid.uuid4()),
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class SubmitPurchaseRequestTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "submit_purchase_request"

    def get_description(self) -> str:
        return "提交一条草稿状态的采购申请，提交后进入待审批状态。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"request_id": {"type": "integer", "description": "采购申请 id"}},
            "required": ["request_id"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        request_id = kwargs.get("request_id")
        try:
            result = hub.call(
                "POST", f"/procurement/requests/{int(request_id)}/submit", user_id, team_id,
                ["procurement.write"], "submit_purchase_request", idempotency_key=str(uuid.uuid4()),
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class ApprovePurchaseRequestTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "approve_purchase_request"

    def get_description(self) -> str:
        return "批准一条已提交的采购申请（只有部门负责人视角的对话该调用这个工具）。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "request_id": {"type": "integer", "description": "采购申请 id"},
                "note": {"type": "string", "description": "审批意见，可选"},
            },
            "required": ["request_id"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        request_id = kwargs.get("request_id")
        try:
            result = hub.call(
                "POST", f"/procurement/requests/{int(request_id)}/approve", user_id, team_id,
                ["procurement.approve"], "approve_purchase_request",
                json_body={"note": kwargs.get("note")}, idempotency_key=str(uuid.uuid4()),
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class RejectPurchaseRequestTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "reject_purchase_request"

    def get_description(self) -> str:
        return "拒绝一条已提交的采购申请（只有部门负责人视角的对话该调用这个工具）。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "request_id": {"type": "integer", "description": "采购申请 id"},
                "note": {"type": "string", "description": "拒绝理由，可选"},
            },
            "required": ["request_id"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        request_id = kwargs.get("request_id")
        try:
            result = hub.call(
                "POST", f"/procurement/requests/{int(request_id)}/reject", user_id, team_id,
                ["procurement.approve"], "reject_purchase_request",
                json_body={"note": kwargs.get("note")}, idempotency_key=str(uuid.uuid4()),
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)


@ToolRegistry.register
class GetPurchaseStatusTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "get_purchase_status"

    def get_description(self) -> str:
        return "查询一条采购申请当前的状态（草稿/已提交/已批准/已拒绝），批准后还会带出生成的采购单信息。"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"request_id": {"type": "integer", "description": "采购申请 id"}},
            "required": ["request_id"],
        }

    def execute(self, **kwargs) -> str:
        try:
            user_id, team_id = _require_user_and_team(self._ctx)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        request_id = kwargs.get("request_id")
        try:
            result = hub.call(
                "GET", f"/procurement/requests/{int(request_id)}", user_id, team_id,
                ["procurement.read"], "get_purchase_status",
            )
        except hub.EnterpriseHubError as exc:
            return _error_json(exc)
        return json.dumps(result, ensure_ascii=False)
