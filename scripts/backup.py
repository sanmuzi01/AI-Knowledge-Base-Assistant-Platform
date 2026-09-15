"""一键备份：MySQL 全库 dump + 应用数据目录打包，写到 backups/ 下。

跟 docs/deployment.md 里手动敲的命令是一回事，只是包装成一个脚本方便配 cron/
计划任务定时跑，并顺手清理过期备份。不备份 Docker 部署下 chroma 具名卷（那是
Docker 自己管的卷，备份方式见 docs/deployment.md 里的说明），只备份本机路径。

用法（项目根目录）：
    .venv/Scripts/python.exe scripts/backup.py
    .venv/Scripts/python.exe scripts/backup.py --keep-days 14   # 清理 14 天前的备份
"""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"

# 相对项目根目录；和 .env(.production).example 里的默认值、docs/deployment.md 第 5 节保持一致。
DATA_DIRS = ["knowledge_files", "vector_db", "chroma_db", "logs", "skills", "skills_packages",
             os.path.join("prompt", "prompts")]


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def dump_mysql(dest: pathlib.Path) -> bool:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "agent_sql")

    if shutil.which("mysqldump") is None:
        print("[跳过] 没找到 mysqldump 命令，请自行导出数据库或把 mysqldump 加进 PATH")
        return False

    cmd = [
        "mysqldump", f"-h{host}", f"-P{port}", f"-u{user}",
        "--single-transaction", "--routines", "--triggers", name,
    ]
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password  # 避免密码出现在进程列表里（-p 参数会被 ps 看到）

    print(f"[dump] mysqldump {name} -> {dest.name}")
    with open(dest, "wb") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        dest.unlink(missing_ok=True)
        print(f"[失败] mysqldump 退出码 {result.returncode}: {result.stderr.decode('utf-8', 'ignore')[:500]}")
        return False
    return True


def archive_data_dirs(dest: pathlib.Path) -> None:
    existing = [d for d in DATA_DIRS if (ROOT / d).exists()]
    if not existing:
        print("[跳过] 没有找到任何数据目录（knowledge_files/vector_db/...），可能都是空的")
        return
    print(f"[archive] {', '.join(existing)} -> {dest.name}")
    with tarfile.open(dest, "w:gz") as tar:
        for d in existing:
            tar.add(ROOT / d, arcname=d)


def cleanup_old_backups(keep_days: int) -> None:
    if keep_days <= 0:
        return
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for item in BACKUP_DIR.glob("*"):
        if item.is_file() and item.stat().st_mtime < cutoff:
            item.unlink()
            removed += 1
    if removed:
        print(f"[清理] 删除了 {removed} 个 {keep_days} 天前的备份文件")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-days", type=int, default=0, help="清理超过多少天的旧备份，0 表示不清理")
    args = parser.parse_args()

    BACKUP_DIR.mkdir(exist_ok=True)
    ts = _timestamp()

    ok = dump_mysql(BACKUP_DIR / f"db_{ts}.sql")
    archive_data_dirs(BACKUP_DIR / f"data_{ts}.tar.gz")
    cleanup_old_backups(args.keep_days)

    print("完成" if ok else "完成（数据库部分被跳过，请检查上面的提示）")


if __name__ == "__main__":
    main()
