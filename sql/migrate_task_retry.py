"""迁移脚本：给 background_task 表加 retry_count + parent_task_id 字段
用 .venv 的 python 执行：.venv\\Scripts\\python.exe sql\\migrate_task_retry.py
幂等：列已存在则跳过
"""
import os
import sys
from pathlib import Path

# 加载 .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# .env 用分字段配置
host = os.environ.get("DB_HOST", "127.0.0.1")
port = int(os.environ.get("DB_PORT", "3306"))
user = os.environ.get("DB_USER", "root")
password = os.environ.get("DB_PASSWORD", "")
db = os.environ.get("DB_NAME", "agent_sql")

# 如果设了 DATABASE_URL 就优先用它
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    from urllib.parse import urlparse
    parsed = urlparse(db_url.replace("mysql+pymysql://", "mysql://"))
    host = parsed.hostname or host
    port = parsed.port or port
    user = parsed.username or user
    password = parsed.password or password
    db = parsed.path.lstrip("/") or db

try:
    import pymysql

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db, charset="utf8mb4")
    cur = conn.cursor()

    # 检查现有列
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='background_task'
    """, (db,))
    existing = {row[0] for row in cur.fetchall()}
    print(f"现有列: {sorted(existing)}")

    to_add = []
    if "retry_count" not in existing:
        to_add.append(("retry_count", "INT NOT NULL DEFAULT 0 COMMENT '本任务被重试过的次数'"))
    if "parent_task_id" not in existing:
        to_add.append(("parent_task_id", "INT NULL COMMENT '重试时指向触发本次重试的原任务ID'"))

    if not to_add:
        print("所有列已存在，无需迁移")
    else:
        cols_sql = ", ".join(f"ADD COLUMN {c} {d}" for c, d in to_add)
        sql = f"ALTER TABLE background_task {cols_sql}"
        print(f"执行: {sql}")
        cur.execute(sql)
        conn.commit()
        print(f"已添加 {len(to_add)} 列: {[c for c, _ in to_add]}")

        # 加外键（如果 parent_task_id 刚加且外键不存在）
        if any(c == "parent_task_id" for c, _ in to_add):
            cur.execute("""
                SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='background_task'
                  AND CONSTRAINT_NAME='fk_task_parent'
            """, (db,))
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE background_task
                    ADD CONSTRAINT fk_task_parent
                    FOREIGN KEY (parent_task_id) REFERENCES background_task(id)
                    ON DELETE SET NULL
                """)
                conn.commit()
                print("已加外键 fk_task_parent")
            else:
                print("外键 fk_task_parent 已存在，跳过")

    # 验证最终列
    cur.execute("""
        SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='background_task'
        ORDER BY ORDINAL_POSITION
    """, (db,))
    print("\n最终表结构:")
    for row in cur.fetchall():
        print(f"  {row[0]:20s} {row[1]:20s} nullable={row[2]:3s} default={row[3]}")

    cur.close()
    conn.close()
    print("\n迁移完成")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
