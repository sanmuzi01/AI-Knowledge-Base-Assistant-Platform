"""Phase 3A（docs/db-migration-plan.md）之后的护栏：不需要真实数据库连接，纯静态检查。

models/init_db.py 里 _run_migrations() 的手写 ALTER TABLE 列表已经冻结——新字段/新表
一律走 Alembic 迁移文件（migrations/versions/），不要在那个列表里继续加条目。这里用
纯源码检查（不调用 _run_migrations() 本身，避免需要真实 DB 连接）确认没人悄悄加回去。
"""
import inspect
import re
import unittest

from models.init_db import _run_migrations

_FROZEN_MIGRATION_COUNT = 30


class RunMigrationsListIsFrozenTest(unittest.TestCase):
    def test_run_migrations_list_is_frozen(self):
        source = inspect.getsource(_run_migrations)
        # 只数第一个 "migrations = [ ... ]" 列表（表名/列名新增字段用的那份），
        # 不数后面 column_type_migrations / index_migrations 这两个单独的小列表。
        match = re.search(r"migrations = \[(.*?)\n {4}\]", source, flags=re.DOTALL)
        self.assertIsNotNone(match, "没找到 migrations 列表，_run_migrations() 的写法是不是变了？")
        entries = re.findall(r'^ {8}\("', match.group(1), flags=re.MULTILINE)
        self.assertEqual(
            len(entries), _FROZEN_MIGRATION_COUNT,
            "models/init_db.py 的 _run_migrations() 列表条目数变了——如果是新加的字段/表，"
            "改成写一个新的 Alembic 迁移文件（migrations/versions/），不要加在这个列表里；"
            "如果确实评审过要继续用这条老路径，同步改这里的 _FROZEN_MIGRATION_COUNT 并说明理由。"
        )


if __name__ == "__main__":
    unittest.main()
