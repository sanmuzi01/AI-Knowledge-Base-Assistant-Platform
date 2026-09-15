"""scripts/seed_demo.py 的生产环境防呆闸门。

用子进程真跑一遍脚本（而不是 import 后调用函数）：这个脚本会在导入 models.init_db
之前，模块级代码里直接检查 APP_ENV 并 sys.exit(1)，子进程是唯一能同时验证
"检查生效" 和 "生效顺序在任何数据库相关 import 之前" 的方式。
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "seed_demo.py"


class SeedDemoGuardTest(unittest.TestCase):
    def _run(self, app_env: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["APP_ENV"] = app_env
        # 让 is_production() 判定明确为真所需的最小变量集合；不需要真的能连上数据库，
        # 因为这个脚本在 APP_ENV=production 时应该在碰数据库之前就退出。
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(ROOT), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )

    def test_refuses_to_run_against_production(self):
        result = self._run("production")
        self.assertEqual(result.returncode, 1)
        self.assertIn("拒绝执行", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
