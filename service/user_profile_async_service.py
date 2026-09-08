"""用户画像异步服务。"""

from typing import Any, Dict

from models.user_profile_async_dao import get_user_profile_async, upsert_user_profile_async
from service.user_profile_service import normalize_profile_payload, profile_to_dict


async def get_user_profile_payload(db, user_id: int) -> Dict[str, Any]:
    profile = await get_user_profile_async(db, user_id)
    return profile_to_dict(profile)


async def save_user_profile(db, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = normalize_profile_payload(payload)
    profile = await upsert_user_profile_async(db, user_id, cleaned)
    await db.commit()
    await db.refresh(profile)
    return profile_to_dict(profile)
