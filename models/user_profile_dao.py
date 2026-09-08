from typing import Optional

from models.init_db import UserProfile


def get_user_profile(db, user_id: int) -> Optional[UserProfile]:
    """读取用户画像；未配置时返回 None。"""
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def upsert_user_profile(db, user_id: int, payload: dict) -> UserProfile:
    """创建或更新用户画像，调用方负责 commit。"""
    profile = get_user_profile(db, user_id)
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    for key, value in payload.items():
        setattr(profile, key, value)
    db.flush()
    return profile

