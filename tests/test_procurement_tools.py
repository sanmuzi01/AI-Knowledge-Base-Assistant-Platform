"""Phase 5：采购 Agent 工具（service/tools/procurement.py）的单测。

跟 tests/test_oa_leave_tools.py 是同一套思路：mock 掉 `hub.call` 和
`_resolve_team_id`，只验证工具层的参数映射/scope/错误转换，不依赖真实的
企业业务中心或 MySQL。真实链路验证在 enterprise-business-hub 自己的
JUnit 集成测试（ProcurementControllerIntegrationTest）里。

采购比请假多一条要测的：当前用户不属于任何部门时，工具应该直接返回错误 JSON，
不应该带着 team_id=None 去调后端（Java 侧 team_id 是必填的）。
"""
import json
import unittest
from unittest.mock import patch

from service import enterprise_hub_client as hub
from service.tools.base import ToolContext
from service.tools.procurement import (
    ApprovePurchaseRequestTool,
    CreatePurchaseDraftTool,
    GetDepartmentBudgetTool,
    GetInventoryStatusTool,
    GetPurchaseStatusTool,
    RejectPurchaseRequestTool,
    SubmitPurchaseRequestTool,
)


def _ctx(user_id=2001):
    return ToolContext(user_id=user_id)


@patch("service.tools.procurement._resolve_team_id", return_value=9)
class ProcurementToolsTest(unittest.TestCase):
    def test_get_inventory_status_builds_read_scope(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"sku": "SKU-1"}) as mock_call:
            tool = GetInventoryStatusTool()
            tool.set_context(_ctx())
            result = tool.execute(sku="SKU-1")
        mock_call.assert_called_once_with(
            "GET", "/procurement/products/SKU-1", 2001, 9, ["procurement.read"], "get_inventory_status",
        )
        self.assertEqual(json.loads(result)["sku"], "SKU-1")

    def test_get_budget_with_year(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"remainingAmount": 500}) as mock_call:
            tool = GetDepartmentBudgetTool()
            tool.set_context(_ctx())
            tool.execute(year=2026)
        mock_call.assert_called_once_with(
            "GET", "/procurement/budget?year=2026", 2001, 9, ["procurement.read"], "get_department_budget",
        )

    def test_create_draft_passes_lines_and_write_scope(self, _team):
        lines = [{"sku": "SKU-1", "quantity": 3}]
        with patch("service.tools.procurement.hub.call", return_value={"id": 1, "status": "DRAFT"}) as mock_call:
            tool = CreatePurchaseDraftTool()
            tool.set_context(_ctx())
            result = tool.execute(lines=lines)
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/procurement/requests", 2001, 9, ["procurement.write"], "create_purchase_draft",
        ))
        self.assertEqual(kwargs["json_body"], {"lines": lines})
        self.assertEqual(json.loads(result)["status"], "DRAFT")

    def test_submit_uses_write_scope(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"status": "SUBMITTED"}) as mock_call:
            tool = SubmitPurchaseRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=7)
        args, _ = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/procurement/requests/7/submit", 2001, 9, ["procurement.write"], "submit_purchase_request",
        ))

    def test_approve_uses_approve_scope(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"status": "APPROVED"}) as mock_call:
            tool = ApprovePurchaseRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=7, note="同意")
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/procurement/requests/7/approve", 2001, 9, ["procurement.approve"], "approve_purchase_request",
        ))
        self.assertEqual(kwargs["json_body"], {"note": "同意"})

    def test_reject_uses_approve_scope(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"status": "REJECTED"}) as mock_call:
            tool = RejectPurchaseRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=7, note="预算紧张")
        args, _ = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/procurement/requests/7/reject", 2001, 9, ["procurement.approve"], "reject_purchase_request",
        ))

    def test_get_status_uses_read_scope(self, _team):
        with patch("service.tools.procurement.hub.call", return_value={"status": "APPROVED"}) as mock_call:
            tool = GetPurchaseStatusTool()
            tool.set_context(_ctx())
            tool.execute(request_id=7)
        args, _ = mock_call.call_args
        self.assertEqual(args[:6], (
            "GET", "/procurement/requests/7", 2001, 9, ["procurement.read"], "get_purchase_status",
        ))

    def test_hub_error_becomes_error_json(self, _team):
        with patch("service.tools.procurement.hub.call",
                   side_effect=hub.EnterpriseHubError(400, "预算不足")):
            tool = SubmitPurchaseRequestTool()
            tool.set_context(_ctx())
            result = tool.execute(request_id=7)
        parsed = json.loads(result)
        self.assertEqual(parsed["error"], "预算不足")
        self.assertEqual(parsed["status_code"], 400)


class ProcurementNoTeamTest(unittest.TestCase):
    """当前用户不属于任何部门——不该带着 team_id=None 去调后端，直接拒绝。"""

    @patch("service.tools.procurement._resolve_team_id", return_value=None)
    def test_no_team_returns_error_without_calling_hub(self, _team):
        with patch("service.tools.procurement.hub.call") as mock_call:
            tool = GetInventoryStatusTool()
            tool.set_context(_ctx())
            result = tool.execute(sku="SKU-1")
        mock_call.assert_not_called()
        self.assertIn("不属于任何部门", json.loads(result)["error"])


if __name__ == "__main__":
    unittest.main()
