import json
import pathlib
import subprocess
import sys
from typing import List

import yaml


ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(command: List[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def parse_configs() -> None:
    print("\n检查 YAML/JSON 配置...")
    yaml_files = [
        "docker-compose.yml",
        "deploy/prometheus.yml",
        "deploy/prometheus-rules.yml",
        "deploy/grafana/provisioning/datasources/prometheus.yml",
        "deploy/grafana/provisioning/dashboards/dashboards.yml",
    ]
    json_files = [
        "deploy/grafana/provisioning/dashboards/json/agent-platform-overview.json",
    ]
    for file_name in yaml_files:
        yaml.safe_load((ROOT / file_name).read_text(encoding="utf-8"))
        print(f"OK {file_name}")
    for file_name in json_files:
        json.loads((ROOT / file_name).read_text(encoding="utf-8"))
        print(f"OK {file_name}")


def check_required_files() -> None:
    print("\n检查上线关键文件...")
    required = [
        ".env.production.example",
        "Dockerfile",
        "frontend/Dockerfile",
        "docker-compose.yml",
        "deploy/nginx.conf",
        "deploy/prometheus.yml",
        "deploy/prometheus-rules.yml",
        "scripts/load_test.py",
        "scripts/crawl_check.py",
        "scripts/backup.ps1",
        "scripts/restore.ps1",
        "alembic.ini",
        "migrations/env.py",
        "migrations/script.py.mako",
        "migrations/versions/20260830_0001_baseline.py",
        "docs/deployment.md",
        "docs/release-checklist.md",
        "docs/load-testing.md",
        "docs/database-migrations.md",
        "docs/backup-restore.md",
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
    parse_configs()
    run([python, "-m", "compileall", "FasdtApi", "service", "models", "utils", "scripts", "tests"])
    run([python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    run(["npm.cmd" if sys.platform.startswith("win") else "npm", "run", "frontend:build"])
    print("\n发布自检完成")


if __name__ == "__main__":
    main()
