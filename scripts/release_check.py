import pathlib
import subprocess
import sys
from typing import List


ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(command: List[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def check_required_files() -> None:
    print("\n检查上线关键文件...")
    required = [
        ".env.production.example",
        "scripts/load_test.py",
        "scripts/crawl_check.py",
        "alembic.ini",
        "migrations/env.py",
        "migrations/script.py.mako",
        "migrations/versions/20260830_0001_baseline.py",
        "docs/deployment.md",
        "docs/release-checklist.md",
        "docs/load-testing.md",
        "docs/database-migrations.md",
        "docs/testing.md",
    ]
    missing = [file_name for file_name in required if not (ROOT / file_name).exists()]
    if missing:
        raise SystemExit("缺少上线关键文件: " + ", ".join(missing))
    for file_name in required:
        print(f"OK {file_name}")


def main() -> None:
    python = sys.executable
    check_required_files()
    run([python, "-m", "compileall", "FasdtApi", "service", "models", "utils", "scripts", "tests"])
    run([python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    run(["npm.cmd" if sys.platform.startswith("win") else "npm", "run", "frontend:build"])
    print("\n发布自检完成")


if __name__ == "__main__":
    main()
