"""企业业务中心（Spring Boot）的手动烟雾测试：签名请求打真实接口，走一遍
OA 请假闭环。不是自动化测试（不接 unittest discover），是本地验证脚本，
用法见 docs/enterprise-business-hub-plan.md。
"""
import base64
import hashlib
import hmac
import json
import time
import uuid

import requests

BASE_URL = "http://127.0.0.1:8090"
SECRET = "dev-only-shared-secret-change-me"


def sign(user_id: int, team_id, scopes: list[str], operation: str) -> dict:
    context = {
        "user_id": user_id,
        "team_id": team_id,
        "scopes": scopes,
        "operation": operation,
        "trace_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "nonce": uuid.uuid4().hex,
    }
    context_b64 = base64.b64encode(json.dumps(context).encode("utf-8")).decode("ascii")
    signature = hmac.new(SECRET.encode("utf-8"), context_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"X-Context": context_b64, "X-Signature": signature}


def call(method, path, user_id, team_id, scopes, operation, **kwargs):
    headers = sign(user_id, team_id, scopes, operation)
    headers.update(kwargs.pop("headers", {}))
    resp = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=10, **kwargs)
    print(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


def main():
    user_id, team_id = 9001, 2

    balances = call("GET", "/oa/leave/balance?year=2026", user_id, team_id, ["oa.leave.read"], "get_leave_balance")
    assert any(b["leaveTypeCode"] == "annual" for b in balances), balances

    draft = call(
        "POST", "/oa/leave/requests", user_id, team_id, ["oa.leave.write"], "create_leave_draft",
        json={"leaveTypeCode": "annual", "startDate": "2026-10-01", "endDate": "2026-10-02", "reason": "烟雾测试"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert draft["status"] == "DRAFT", draft
    request_id = draft["id"]

    submitted = call(
        "POST", f"/oa/leave/requests/{request_id}/submit", user_id, team_id, ["oa.leave.write"],
        "submit_leave_request", headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert submitted["status"] == "SUBMITTED", submitted

    approver_id = 9002
    approved = call(
        "POST", f"/oa/leave/requests/{request_id}/approve", approver_id, team_id, ["oa.leave.approve"],
        "approve_leave_request", json={"note": "同意"}, headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert approved["status"] == "APPROVED", approved

    status = call("GET", f"/oa/leave/requests/{request_id}", user_id, team_id, ["oa.leave.read"], "get_leave_status")
    assert status["status"] == "APPROVED", status

    new_balances = call("GET", "/oa/leave/balance?year=2026", user_id, team_id, ["oa.leave.read"], "get_leave_balance")
    annual = next(b for b in new_balances if b["leaveTypeCode"] == "annual")
    assert annual["remainingDays"] == 8.0, new_balances  # 10 - 2 天

    print("\n[PASS] OA 请假闭环走通：查余额(10) -> 建草稿 -> 提交 -> 批准 -> 查状态 -> 余额扣减(8)")


if __name__ == "__main__":
    main()
