"""Phase 3A 的 CI 护栏：确认 Alembic 迁移链跟 models/init_db.py 的 Base.metadata 没有漂移。

用法（假定当前数据库已经是一个刚跑完 `alembic upgrade head` 的空库/CI 库）：

    python scripts/check_no_migration_drift.py

做的事：对着当前数据库跑一次 `alembic revision --autogenerate`，检查生成的迁移文件
upgrade()/downgrade() 是不是只有 "pass"（= 没有检测到任何变化）。如果不是空的，说明
模型改了却没写对应的 Alembic 迁移——这一步失败，并把检测到的变化摘要打印出来方便定位，
生成的探测文件不管成功还是失败都会删掉，不留垃圾文件。

跟本地手动核对 Phase 3A 时用的方法完全一样（见 docs/db-migration-plan.md），只是包成
一个脚本方便 CI 调用，避免每次手写一遍。
"""
import re
import subprocess
import sys
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def main() -> int:
    before = set(VERSIONS_DIR.glob("*.py"))

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "ci drift probe"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print("[FAIL] alembic revision --autogenerate 本身执行失败，见上面的输出", file=sys.stderr)
        return 1

    after = set(VERSIONS_DIR.glob("*.py"))
    new_files = after - before
    if not new_files:
        print("[FAIL] 没有生成探测文件，检查 alembic 配置是否正常", file=sys.stderr)
        return 1

    ok = True
    for path in new_files:
        text = path.read_text(encoding="utf-8")
        upgrade_body = re.search(r"def upgrade\(\).*?def downgrade\(\)", text, re.DOTALL)
        body_text = upgrade_body.group(0) if upgrade_body else text
        # 生成的 upgrade() 里除了注释和 "pass" 之外还有别的代码，说明检测到了真实变化。
        meaningful_lines = [
            line.strip() for line in body_text.splitlines()
            if line.strip() and not line.strip().startswith("#") and "def upgrade" not in line
            and "def downgrade" not in line and line.strip() != "pass"
        ]
        if meaningful_lines:
            ok = False
            print(f"[FAIL] {path.name} 检测到模型和迁移链之间有漂移，摘要：", file=sys.stderr)
            for line in meaningful_lines:
                print(f"    {line}", file=sys.stderr)
        path.unlink()  # 探测文件不管成功还是失败都不留

    if ok:
        print("[PASS] 数据库结构跟 Base.metadata 完全一致，没有漂移")
        return 0
    print(
        "\n模型改了但没写 Alembic 迁移文件——新增字段/表请补一个 migrations/versions/ 下的"
        "迁移文件，不要指望 create_all() 兜底（见 docs/db-migration-plan.md）。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
