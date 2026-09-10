"""删掉库里所有 `rt_%` 测试用户及其级联数据（真实用户不受影响）。

路由级测试每跑一次会在真实库里建几十个 `rt_*` 用户，正常由 tearDownClass 清掉；
中断 / 报错时会残留。这个脚本用来手动清一遍。

用法（在项目根目录）：
    .venv/Scripts/python.exe scripts/purge_test_users.py --dry-run
    .venv/Scripts/python.exe scripts/purge_test_users.py --yes
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from models.init_db import SessionLocal  # noqa: E402


def _count() -> int:
    db = SessionLocal()
    try:
        return db.execute(text(r"SELECT COUNT(*) FROM `user` WHERE name LIKE 'rt\_%'")).scalar() or 0
    finally:
        db.close()


def main() -> int:
    n = _count()
    print(f"当前 rt_* 测试用户：{n}")
    if n == 0:
        return 0
    if "--yes" not in sys.argv:
        print("加 --yes 执行删除；不传只统计。")
        return 0
    from tests._route_client import sweep_test_users
    deleted = sweep_test_users()
    print(f"已删除 {deleted} 个测试用户，剩余 {_count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
