"""一次性迁移：把 user 表里残留的明文口令转成 bcrypt 哈希。

背景：历史版本登录时允许「存储值不是 bcrypt 哈希就按明文比对，并顺手升级」。
该兜底分支已从 service/auth_service.py / auth_async_service.py 移除，
非 bcrypt 的存储值现在一律登录失败。上线新版本前，需要先跑一次本脚本，
把所有非哈希口令就地转成 bcrypt，避免存量用户被锁在门外。

用法（项目根目录）：

    .venv\\Scripts\\python.exe -m scripts.migrate_plaintext_passwords          # 预演，只统计
    .venv\\Scripts\\python.exe -m scripts.migrate_plaintext_passwords --apply  # 实际写库

幂等：已是 bcrypt 哈希的行会被跳过，可反复执行。
"""
import argparse
import sys

from models.init_db import SessionLocal, User
from service.auth_service import hash_password, is_bcrypt_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="把 user 表明文口令迁移为 bcrypt 哈希")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写库；不加该参数只做预演统计",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        users = db.query(User).all()
        total = len(users)
        legacy = [u for u in users if not is_bcrypt_hash(u.password or "")]

        print(f"用户总数: {total}")
        print(f"非 bcrypt（待迁移）: {len(legacy)}")
        for u in legacy:
            print(f"  - id={u.id} name={u.name}")

        if not legacy:
            print("没有需要迁移的记录。")
            return 0

        if not args.apply:
            print("\n预演模式，未写库。确认无误后加 --apply 重新执行。")
            return 0

        for u in legacy:
            u.password = hash_password(u.password or "")
        db.commit()
        print(f"\n已迁移 {len(legacy)} 条记录为 bcrypt 哈希。")
        return 0
    except Exception as exc:  # noqa: BLE001 - 顶层脚本，打印后非零退出
        db.rollback()
        print(f"迁移失败: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
