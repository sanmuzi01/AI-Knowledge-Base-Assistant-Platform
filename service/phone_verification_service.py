import hashlib
import hmac
import json
import os
import random
import re
import time
from typing import Dict, Optional
from urllib import request as urllib_request

from fastapi import HTTPException, status

from utils.cache import verification_cache
from utils.logger_handler import logger
from utils.rate_limit import LimitExceeded, require_limit

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，配置缺失或格式错误时使用默认值。"""

    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def normalize_phone(phone: str) -> str:
    """规范化中国大陆手机号，只保留数字并校验格式。"""

    normalized = re.sub(r"\D", "", phone or "")
    if not PHONE_PATTERN.fullmatch(normalized):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请输入有效的手机号")
    return normalized


def _cache_key(phone: str) -> tuple:
    return "sms_register", phone


def _code_digest(phone: str, code: str) -> str:
    """用服务端密钥保存验证码摘要，避免缓存泄露时直接暴露明文验证码。"""

    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("LLM_ENCRYPTION_KEY") or "dev-secret"
    payload = f"{phone}:{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _now() -> int:
    return int(time.time())


def _send_by_webhook(phone: str, code: str, ttl_seconds: int) -> None:
    """通过通用 Webhook 发送短信，方便上线时接入任意短信服务网关。"""

    webhook_url = os.getenv("SMS_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("未配置 SMS_WEBHOOK_URL")

    payload = json.dumps({
        "phone": phone,
        "code": code,
        "ttl_seconds": ttl_seconds,
        "scene": "register",
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.getenv("SMS_WEBHOOK_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib_request.Request(webhook_url, data=payload, headers=headers, method="POST")
    timeout = float(os.getenv("SMS_WEBHOOK_TIMEOUT", "3"))
    with urllib_request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"短信服务返回异常状态: {resp.status}")


def _send_sms(phone: str, code: str, ttl_seconds: int) -> Dict[str, Optional[str]]:
    """发送验证码。

    SMS_PROVIDER=webhook 时走真实短信网关；默认 console 模式只写日志，便于本地开发测试。
    """

    provider = os.getenv("SMS_PROVIDER", "console").strip().lower()
    if provider == "webhook":
        _send_by_webhook(phone, code, ttl_seconds)
        return {"provider": "webhook", "dev_code": None}

    logger.info(f"注册短信验证码: phone={phone}, code={code}, ttl={ttl_seconds}s")
    dev_code = code if os.getenv("SMS_EXPOSE_DEV_CODE", "0") == "1" else None
    return {"provider": "console", "dev_code": dev_code}


def send_register_code(phone: str, client_ip: str = "") -> Dict[str, object]:
    """发送注册验证码，并限制同一手机号和 IP 的发送频率。"""

    normalized = normalize_phone(phone)
    ttl_seconds = _env_int("SMS_CODE_TTL_SECONDS", 300)
    interval_seconds = _env_int("SMS_CODE_SEND_INTERVAL_SECONDS", 60)

    try:
        require_limit(
            key=f"sms:register:phone:{normalized}",
            limit_env="SMS_CODE_PHONE_LIMIT",
            default_limit=1,
            window_env="SMS_CODE_PHONE_WINDOW_SECONDS",
            default_window=interval_seconds,
            label="验证码发送",
        )
        if client_ip:
            require_limit(
                key=f"sms:register:ip:{client_ip}",
                limit_env="SMS_CODE_IP_LIMIT",
                default_limit=20,
                window_env="SMS_CODE_IP_WINDOW_SECONDS",
                default_window=3600,
                label="验证码发送",
            )
        require_limit(
            key=f"sms:register:daily:{normalized}",
            limit_env="SMS_CODE_DAILY_LIMIT",
            default_limit=10,
            window_env="SMS_CODE_DAILY_WINDOW_SECONDS",
            default_window=86400,
            label="验证码发送",
        )
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
            headers={"Retry-After": str(exc.retry_after)},
        )

    code = _new_code()
    sent = _send_sms(normalized, code, ttl_seconds)
    verification_cache.set(
        _cache_key(normalized),
        {
            "digest": _code_digest(normalized, code),
            "attempts": 0,
            "created_at": _now(),
            "expires_at": _now() + ttl_seconds,
        },
        ttl=ttl_seconds,
    )
    return {
        "message": "验证码已发送",
        "phone": normalized,
        "expires_in": ttl_seconds,
        "retry_after": interval_seconds,
        "provider": sent["provider"],
        "dev_code": sent["dev_code"],
    }


def verify_register_code(phone: str, code: str, consume: bool = True) -> str:
    """校验注册验证码，成功后默认立即失效。"""

    normalized = normalize_phone(phone)
    clean_code = re.sub(r"\D", "", code or "")
    if not re.fullmatch(r"\d{6}", clean_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请输入 6 位短信验证码")

    record = verification_cache.get(_cache_key(normalized))
    if not record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证码已过期，请重新获取")

    max_attempts = _env_int("SMS_CODE_MAX_VERIFY_ATTEMPTS", 5)
    expires_at = int(record.get("expires_at") or 0)
    remaining_ttl = expires_at - _now()
    if remaining_ttl <= 0:
        verification_cache.invalidate(_cache_key(normalized))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证码已过期，请重新获取")

    attempts = int(record.get("attempts") or 0) + 1
    expected = record.get("digest") or ""
    actual = _code_digest(normalized, clean_code)
    if not hmac.compare_digest(expected, actual):
        if attempts >= max_attempts:
            verification_cache.invalidate(_cache_key(normalized))
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证码错误次数过多，请重新获取")
        record["attempts"] = attempts
        verification_cache.set(_cache_key(normalized), record, ttl=remaining_ttl)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    if consume:
        verification_cache.invalidate(_cache_key(normalized))
    return normalized
