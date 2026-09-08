"""手机验证码异步服务。

验证码缓存逻辑仍复用同步实现；发送短信可能访问外部 Webhook，
因此通过线程池执行，避免阻塞 FastAPI 事件循环。
"""

from starlette.concurrency import run_in_threadpool

from service.phone_verification_service import (
    normalize_phone,
    send_register_code,
    verify_register_code,
)


async def async_send_register_code(phone: str, client_ip: str = ""):
    normalized_phone = normalize_phone(phone)
    return await run_in_threadpool(send_register_code, normalized_phone, client_ip)


async def async_verify_register_code(phone: str, code: str, consume: bool = True) -> str:
    return await run_in_threadpool(verify_register_code, phone, code, consume)
