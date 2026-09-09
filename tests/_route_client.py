"""真实路由级测试的共享脚手架。

不是测试文件（不匹配 test_*.py），提供：
- TestClient(app)（触发 lifespan / bootstrap_database）
- 直接建测试用户（bcrypt 落库）+ 签发真实 JWT
- 结束后清理这批用户及其组件 / Agent / 知识

依赖本地可连的 MySQL 与 .env 里的 JWT_SECRET_KEY —— 与 CI 的单测环境一致。
无法连库时，调用方应 skip（见 route_tests_available）。
"""

import os
import sys
import time
import uuid

# FasdtApi.main 在模块导入时就会 assert_runtime_config() —— 用非生产环境跑，避免生产校验拦截。
_ORIG_APP_ENV = os.environ.get("APP_ENV")
os.environ["APP_ENV"] = "test"
# TestClient 默认 Host 是 testserver —— 必须在 import FasdtApi.main（构造 TrustedHostMiddleware）之前放行
os.environ.setdefault("TRUSTED_HOSTS", "127.0.0.1,localhost,api")
if "testserver" not in os.environ["TRUSTED_HOSTS"]:
    os.environ["TRUSTED_HOSTS"] = os.environ["TRUSTED_HOSTS"] + ",testserver"
os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://testserver")

_SUFFIX = f"{int(time.time()) % 100000}{uuid.uuid4().hex[:4]}"
_created_user_ids: list[int] = []


def route_tests_available() -> tuple[bool, str]:
    if not os.getenv("JWT_SECRET_KEY"):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:  # noqa: BLE001
            pass
    if not os.getenv("JWT_SECRET_KEY"):
        return False, "缺少 JWT_SECRET_KEY"
    try:
        from models.init_db import SessionLocal
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception as exc:  # noqa: BLE001
        return False, f"数据库不可用: {exc}"
    return True, ""


def make_client():
    from fastapi.testclient import TestClient
    # 别的测试可能刚把 APP_ENV 改成 production 且没还原 —— import main 会跑生产校验，这里强制非生产
    os.environ["APP_ENV"] = "test"
    # 若 main 已被别的测试以旧 TRUSTED_HOSTS / APP_ENV 导入过，重新导入
    sys.modules.pop("FasdtApi.main", None)
    from FasdtApi.main import app
    return TestClient(app)


def create_user(name_prefix: str, password: str = "Passw0rd!", *, admin: bool = False) -> dict:
    """建一个测试用户，返回 {id, name, password, headers}。"""
    from models.init_db import SessionLocal
    from models.user_dao import create_user as dao_create_user
    from service.auth_service import hash_password
    from service.auth import create_access_token

    name = f"rt_{name_prefix}_{_SUFFIX}"[:20]
    db = SessionLocal()
    try:
        user = dao_create_user(db, name=name, password=hash_password(password), age=30, phone=None)
        uid = user.id
    finally:
        db.close()
    _created_user_ids.append(uid)
    token = create_access_token({"user_id": uid})
    return {
        "id": uid,
        "name": name,
        "password": password,
        "headers": {"Authorization": f"Bearer {token}"},
        "admin": admin,
    }


def admin_env(*names: str):
    """上下文：把给定用户名并入 ADMIN_USER_NAMES。"""
    from unittest.mock import patch
    current = os.getenv("ADMIN_USER_NAMES", "admin")
    merged = ",".join([current, *names])
    return patch.dict(os.environ, {"ADMIN_USER_NAMES": merged})


def cleanup():
    """删除本模块建的用户及其级联数据。测试类 tearDownClass 调用。"""
    if not _created_user_ids:
        return
    import pathlib
    from sqlalchemy import text
    from models.init_db import SessionLocal
    db = SessionLocal()
    try:
        ids = tuple(_created_user_ids)
        in_clause = "(" + ",".join(str(i) for i in ids) + ")"
        # 先删测试 Agent 写出的提示词文件
        agent_ids = [row[0] for row in db.execute(text(f"SELECT id FROM agent WHERE user_id IN {in_clause}")).all()]
        prompts_dir = pathlib.Path(__file__).resolve().parents[1] / "prompt" / "prompts"
        for aid in agent_ids:
            (prompts_dir / f"{aid}.yaml").unlink(missing_ok=True)
        # 组件 + 数据点
        db.execute(text(f"DELETE dp FROM widget_data_points dp JOIN user_widgets w ON dp.widget_id=w.id WHERE w.user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM user_widgets WHERE user_id IN {in_clause}"))
        # 知识文档：按 user_id 统一删（覆盖 agent 私有库 + 空间库；agent_id 可能为 NULL）
        krows = db.execute(text(f"SELECT id, file_path FROM knowledge WHERE user_id IN {in_clause}")).all()
        kids = [r[0] for r in krows]
        for _kid, fpath in krows:
            try:
                if fpath:
                    pathlib.Path(fpath).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
        if kids:
            kin = "(" + ",".join(str(i) for i in kids) + ")"
            db.execute(text(f"DELETE FROM knowledge_chunk WHERE knowledge_id IN {kin}"))
            db.execute(text(f"DELETE FROM background_task WHERE target_type='knowledge' AND target_id IN {kin}"))
        db.execute(text(f"DELETE FROM background_task WHERE user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM knowledge WHERE user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM rag_debug_samples WHERE user_id IN {in_clause}"))
        # 知识库空间 + Agent 绑定
        db.execute(text(f"DELETE aks FROM agent_knowledge_space aks JOIN knowledge_spaces s ON aks.space_id=s.id WHERE s.user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM knowledge_spaces WHERE user_id IN {in_clause}"))
        db.execute(text(f"UPDATE `user` SET selected_agent_id=NULL WHERE id IN {in_clause}"))
        db.execute(text(f"DELETE FROM agent WHERE user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM user_role WHERE user_id IN {in_clause}"))
        db.execute(text(f"DELETE FROM `user` WHERE id IN {in_clause}"))
        db.commit()
    except Exception:  # noqa: BLE001 - 清理尽力而为
        db.rollback()
    finally:
        db.close()
        _created_user_ids.clear()
        if _ORIG_APP_ENV is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = _ORIG_APP_ENV
