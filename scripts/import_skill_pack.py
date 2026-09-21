"""在服务器上把预制 Skill 包导入到管理员账号（不用先把 zip 下载到自己电脑再在网页上传）。

用法（在服务器的项目目录，进容器里跑，容器里已经有数据库连接和 skill 卷）：

    docker compose -f docker-compose.prod.yml exec api \
        python scripts/import_skill_pack.py skill-packs/anbeime-skills-all.zip --admin admin --public

    --admin    导入到哪个管理员账号（默认取环境变量 ADMIN_USERNAME，再默认 admin）
    --public   同时公开到「能力商店」（不加就只放在管理员自己的「我的能力」里）
    --replace  这个管理员已经有同名 Skill 时，先删掉旧的再导入（重复执行、升级预制包时用）

不加 --replace 时遇到同名 Skill 会拒绝导入并列出重名的，避免悄悄产生重复。
"""
import argparse
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def zip_skill_names(path: str):
    from service.skills_core.package_import import parse_skill_md

    names = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if not info.is_dir() and info.filename.replace("\\", "/").split("/")[-1].lower() == "skill.md":
                meta, _ = parse_skill_md(zf.read(info).decode("utf-8-sig", errors="replace"))
                if meta.get("name"):
                    names.append(str(meta["name"]).strip())
    return names


def remove_skill_files(config_file: str) -> None:
    """删 Skill 记录不会删磁盘上的配置和脚本包，替换时一并清掉，免得越积越多。"""
    from service.skills.loader import SKILLS_ROOT

    yml = os.path.join(SKILLS_ROOT, *config_file.split("/"))
    if config_file.startswith("imported/") and os.path.exists(yml):
        os.remove(yml)
    stem = os.path.splitext(os.path.basename(config_file))[0]
    if config_file.startswith("imported/"):
        shutil.rmtree(os.path.join(os.path.dirname(SKILLS_ROOT), "skills_packages", "imported", stem), ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip_path")
    ap.add_argument("--admin", default=os.getenv("ADMIN_USERNAME", "admin"))
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--replace", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.zip_path):
        print(f"找不到文件：{args.zip_path}（如果是刚拉的代码，记得先重新构建镜像：docker compose build api）")
        return 1

    from models.init_db import SessionLocal, User
    from models.skill_dao import list_skills_by_user
    from service.admin_service import is_admin_user
    from service.skills_core.crud import delete_skill
    from service.skills_core.package_import import SkillImportError, import_skill_bundle

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.name == args.admin).first()
        if not admin:
            print(f"找不到账号「{args.admin}」，请用 --admin 指定管理员用户名")
            return 1
        if not is_admin_user(admin):
            print(f"「{args.admin}」不是管理员。脚本和「公开到能力商店」只有管理员能用，请换一个管理员账号")
            return 1

        wanted = set(zip_skill_names(args.zip_path))
        existing = [s for s in list_skills_by_user(db, admin.id) if s.name in wanted]
        if existing and not args.replace:
            print(f"「{args.admin}」名下已经有 {len(existing)} 个同名 Skill（如：{', '.join(s.name for s in existing[:5])}）。")
            print("要覆盖请加 --replace；只想补缺的，请先在后台把重名的删掉。")
            return 2
        for s in existing:
            config_file = s.config_file
            if delete_skill(db, s.id, user_id=admin.id):
                remove_skill_files(config_file)
        if existing:
            print(f"已删除旧的同名 Skill {len(existing)} 个")

        with open(args.zip_path, "rb") as f:
            content = f.read()
        try:
            result = import_skill_bundle(
                db, admin.id, os.path.basename(args.zip_path), content,
                is_public=1 if args.public else 0, allow_scripts=True,
            )
        except SkillImportError as e:
            print(f"导入失败：{e}")
            return 1
    finally:
        db.close()

    imported, failed = result["imported"], result["failed"]
    print(f"导入完成：成功 {len(imported)} 个，失败 {len(failed)} 个；" + ("已公开到能力商店" if args.public else "未公开（只在管理员的「我的能力」里）"))
    status = {}
    for s in imported:
        status[s.get("script_status", "none")] = status.get(s.get("script_status", "none"), 0) + 1
    text = {"none": "纯说明", "ready": "脚本全部可运行", "partial": "部分脚本可运行", "unsupported": "脚本暂不支持"}
    print("脚本状态：" + "，".join(f"{text.get(k, k)} {v}" for k, v in sorted(status.items())))
    for f_ in failed:
        print(f"  失败：{f_['name']}：{f_['error']}")
    return 0 if not failed else 3


if __name__ == "__main__":
    sys.exit(main())
