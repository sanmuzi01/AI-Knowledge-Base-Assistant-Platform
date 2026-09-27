"""Phase 5：OA 请假 Agent 工具（service/tools/oa_leave.py）的单测。

不依赖真实的企业业务中心（Spring Boot）或 MySQL——`enterprise_hub_client.call` 和
`_resolve_team_id` 都打桩，只验证工具层自己的职责：参数怎么映射成请求体、
成功怎么转 JSON、`EnterpriseHubError` 怎么转成给 LLM 看的错误 JSON。真实的端到端
链路验证见 `scripts/smoke_test_enterprise_hub.py`（需要真的起 Java 服务）和
`enterprise-business-hub` 自己的 JUnit 集成测试。
"""
import json
import unittest
from unittest.mock import patch

from service import enterprise_hub_client as hub
from service.tools.base import ToolContext
from service.tools.oa_leave import (
    ApproveLeaveRequestTool,
    CreateLeaveDraftTool,
    GetLeaveBalanceTool,
    GetLeaveStatusTool,
    RejectLeaveRequestTool,
    SubmitLeaveRequestTool,
)


def _ctx(user_id=1001):
    return ToolContext(user_id=user_id)


@patch("service.tools.oa_leave._resolve_team_id", return_value=7)
class OaLeaveToolsTest(unittest.TestCase):
    def test_get_balance_builds_read_scope_and_year_query(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value=[{"leaveTypeCode": "annual"}]) as mock_call:
            tool = GetLeaveBalanceTool()
            tool.set_context(_ctx())
            result = tool.execute(year=2026)
        mock_call.assert_called_once_with(
            "GET", "/oa/leave/balance?year=2026", 1001, 7, ["oa.leave.read"], "get_leave_balance",
        )
        self.assertEqual(json.loads(result), [{"leaveTypeCode": "annual"}])

    def test_get_balance_without_year_omits_query(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value=[]) as mock_call:
            tool = GetLeaveBalanceTool()
            tool.set_context(_ctx())
            tool.execute()
        mock_call.assert_called_once_with(
            "GET", "/oa/leave/balance", 1001, 7, ["oa.leave.read"], "get_leave_balance",
        )

    def test_create_draft_maps_fields_and_write_scope(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value={"id": 1, "status": "DRAFT"}) as mock_call:
            tool = CreateLeaveDraftTool()
            tool.set_context(_ctx())
            result = tool.execute(leave_type_code="annual", start_date="2026-10-01",
                                   end_date="2026-10-02", reason="测试")
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], ("POST", "/oa/leave/requests", 1001, 7, ["oa.leave.write"], "create_leave_draft"))
        self.assertEqual(kwargs["json_body"], {
            "leaveTypeCode": "annual", "startDate": "2026-10-01", "endDate": "2026-10-02", "reason": "测试",
        })
        self.assertIn("idempotency_key", kwargs)
        self.assertEqual(json.loads(result)["status"], "DRAFT")

    def test_submit_uses_write_scope_and_path(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value={"status": "SUBMITTED"}) as mock_call:
            tool = SubmitLeaveRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=42)
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/oa/leave/requests/42/submit", 1001, 7, ["oa.leave.write"], "submit_leave_request",
        ))

    def test_approve_uses_approve_scope(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value={"status": "APPROVED"}) as mock_call:
            tool = ApproveLeaveRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=42, note="同意")
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/oa/leave/requests/42/approve", 1001, 7, ["oa.leave.approve"], "approve_leave_request",
        ))
        self.assertEqual(kwargs["json_body"], {"note": "同意"})

    def test_reject_uses_approve_scope(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value={"status": "REJECTED"}) as mock_call:
            tool = RejectLeaveRequestTool()
            tool.set_context(_ctx())
            tool.execute(request_id=42, note="人手不够")
        args, kwargs = mock_call.call_args
        self.assertEqual(args[:6], (
            "POST", "/oa/leave/requests/42/reject", 1001, 7, ["oa.leave.approve"], "reject_leave_request",
        ))

    def test_get_status_uses_read_scope(self, _team):
        with patch("service.tools.oa_leave.hub.call", return_value={"status": "APPROVED"}) as mock_call:
            tool = GetLeaveStatusTool()
            tool.set_context(_ctx())
            tool.execute(request_id=42)
        args, _ = mock_call.call_args
        self.assertEqual(args[:6], (
            "GET", "/oa/leave/requests/42", 1001, 7, ["oa.leave.read"], "get_leave_status",
        ))

    def test_hub_error_becomes_error_json_not_exception(self, _team):
        with patch("service.tools.oa_leave.hub.call", side_effect=hub.EnterpriseHubError(400, "余额不足")):
            tool = SubmitLeaveRequestTool()
            tool.set_context(_ctx())
            result = tool.execute(request_id=1)
        parsed = json.loads(result)
        self.assertEqual(parsed["error"], "余额不足")
        self.assertEqual(parsed["status_code"], 400)

    def test_missing_context_raises_value_error(self, _team):
        tool = GetLeaveBalanceTool()
        # 不调用 set_context —— 模拟工具被直接调用、没有 ToolExecutor 注入上下文的情况
        with self.assertRaises(ValueError):
            tool.execute()


class SignContextTest(unittest.TestCase):
    def test_signature_is_deterministic_hmac_over_base64_payload(self):
        import base64
        import hashlib
        import hmac as hmac_module

        with patch("service.enterprise_hub_client._secret", return_value="unit-test-secret"):
            headers = hub.sign_context(1, 2, ["a.b"], "op")
        payload = headers["X-Context"]
        expected_sig = hmac_module.new(
            b"unit-test-secret", payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(headers["X-Signature"], expected_sig)

        decoded = json.loads(base64.b64decode(payload))
        self.assertEqual(decoded["user_id"], 1)
        self.assertEqual(decoded["team_id"], 2)
        self.assertEqual(decoded["scopes"], ["a.b"])
        self.assertEqual(decoded["operation"], "op")
        self.assertIn("nonce", decoded)
        self.assertIn("timestamp", decoded)


if __name__ == "__main__":
    unittest.main()
