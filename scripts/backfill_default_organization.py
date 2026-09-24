"""Phase 3B 数据回填（docs/enterprise-rbac-plan.md 1.5 节第 3、4 步）：

1. 建 1 行 organizations（"默认企业"），owner_user_id 填第一个平台管理员（没有管理员
   就填 id 最小的用户；一个用户都没有就只建企业行，不做后面几步）。
2. 把所有现有用户批量插入 organization_members：平台管理员 role=owner，其余 role=member。
3. 把所有 organization_id 为空的 knowledge_spaces 批量挂到默认企业下。

这是运营性质的一次性数据迁移，不是 schema 迁移（表结构由
migrations/versions/20260924_0002_enterprise_rbac_tables.py 负责），单独写成脚本、
可以重复执行不出错：
- 已经有"默认企业"就复用，不会建第二个。
- 用户已经在 organization_members 里就跳过（唯一索引 uq_org_member 兜底）。
- knowledge_spaces 只回填 organization_id 为 NULL 的行，不覆盖已经手动设置过的。

用法（在项目根目录）：
    .venv/Scripts/python.exe scripts/backfill_default_organization.py --dry-run
    .venv/Scripts/python.exe scripts/backfill_default_organization.py --yes
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from models.enterprise_dao import DEFAULT_ORG_NAME  # noqa: E402
from models.init_db import SessionLocal, User  # noqa: E402
from service.admin_service import is_admin_user  # noqa: E402


def _find_or_prepare_default_org(db) -> dict:
    """返回 {"id": int|None, "exists": bool, "owner_user_id": int|None}，不做任何写入。"""
    row = db.execute(
        text("SELECT id FROM organizations WHERE name = :name ORDER BY id LIMIT 1"),
        {"name": DEFAULT_ORG_NAME},
    ).first()
    if row:
        return {"id": row[0], "exists": True, "owner_user_id": None}

    users = db.execute(text("SELECT id, name FROM `user` ORDER BY id")).fetchall()
    owner_user_id = None
    for uid, _name in users:
        user = db.get(User, uid)
        if is_admin_user(user):
            owner_user_id = uid
            break
    if owner_user_id is None and users:
        owner_user_id = users[0][0]
    return {"id": None, "exists": False, "owner_user_id": owner_user_id}


def run(*, dry_run: bool) -> None:
    db = SessionLocal()
    try:
        plan = _find_or_prepare_default_org(db)
        if plan["exists"]:
            org_id = plan["id"]
            print(f"[跳过] 默认企业已存在：organizations.id={org_id}")
        else:
            if plan["owner_user_id"] is None:
                print("[停止] 库里一个用户都没有，不建默认企业（没有 owner_user_id 可填）")
                return
            print(f"[计划] 建默认企业，owner_user_id={plan['owner_user_id']}")
            if dry_run:
                org_id = None
            else:
                db.execute(
                    text(
                        "INSERT INTO organizations (name, owner_user_id, status, created_at) "
                        "VALUES (:name, :owner, 'active', NOW())"
                    ),
                    {"name": DEFAULT_ORG_NAME, "owner": plan["owner_user_id"]},
                )
                db.commit()
                org_id = db.execute(
                    text("SELECT id FROM organizations WHERE name = :name ORDER BY id DESC LIMIT 1"),
                    {"name": DEFAULT_ORG_NAME},
                ).scalar()
                print(f"[完成] organizations.id={org_id}")

        owner_role_id = db.execute(
            text("SELECT id FROM enterprise_role WHERE scope='organization' AND code='owner'")
        ).scalar()
        member_role_id = db.execute(
            text("SELECT id FROM enterprise_role WHERE scope='organization' AND code='member'")
        ).scalar()
        if owner_role_id is None or member_role_id is None:
            print("[停止] enterprise_role 里没有 organization/owner 或 organization/member——"
                  "先跑 migrations/versions/20260924_0002_enterprise_rbac_tables.py 的迁移")
            return

        # org_id 为 None 说明是 dry-run 且默认企业还没真的建出来——这种情况下还没有任何
        # organization_members 行挂在它下面，直接当空集合处理，方便 dry-run 也能把后面
        # 几步的数量预览出来，而不是走到这里就中断。
        existing_member_ids = set()
        if org_id is not None:
            existing_member_ids = {
                row[0] for row in db.execute(
                    text("SELECT user_id FROM organization_members WHERE organization_id=:org"),
                    {"org": org_id},
                ).fetchall()
            }
        users = db.execute(text("SELECT id FROM `user` ORDER BY id")).fetchall()
        to_add = []
        for (uid,) in users:
            if uid in existing_member_ids:
                continue
            user = db.get(User, uid)
            role_id = owner_role_id if is_admin_user(user) else member_role_id
            to_add.append((uid, role_id))

        print(f"[计划] 新增 organization_members {len(to_add)} 条（已有 {len(existing_member_ids)} 条）")
        if not dry_run:
            for uid, role_id in to_add:
                db.execute(
                    text(
                        "INSERT INTO organization_members "
                        "(organization_id, user_id, role_id, status, created_at, updated_at) "
                        "VALUES (:org, :uid, :role, 'active', NOW(), NOW())"
                    ),
                    {"org": org_id, "uid": uid, "role": role_id},
                )
            db.commit()
            print(f"[完成] 新增 {len(to_add)} 条 organization_members")

        pending_spaces = db.execute(
            text("SELECT COUNT(*) FROM knowledge_spaces WHERE organization_id IS NULL")
        ).scalar()
        print(f"[计划] 回填 knowledge_spaces.organization_id：{pending_spaces} 条")
        if not dry_run and pending_spaces:
            db.execute(
                text("UPDATE knowledge_spaces SET organization_id=:org WHERE organization_id IS NULL"),
                {"org": org_id},
            )
            db.commit()
            print(f"[完成] 回填 {pending_spaces} 条 knowledge_spaces.organization_id")
    finally:
        db.close()


def main() -> int:
    dry_run = "--yes" not in sys.argv
    if dry_run:
        print("=== 干跑模式（不写库），加 --yes 才真正执行 ===")
    run(dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
