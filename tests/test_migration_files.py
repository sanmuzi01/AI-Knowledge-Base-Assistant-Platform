import configparser
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent


class MigrationFilesTestCase(unittest.TestCase):
    def test_alembic_files_are_present(self):
        expected = [
            ROOT / "alembic.ini",
            ROOT / "migrations" / "env.py",
            ROOT / "migrations" / "script.py.mako",
            # Phase 3A（docs/db-migration-plan.md）之后：真正可信的基线是这一个，
            # 老的 0001~0008 已经搬去 migrations/archive_pre_baseline/ 存档，不再参与
            # alembic upgrade。
            ROOT / "migrations" / "versions" / "20260924_0001_trusted_baseline.py",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"缺少迁移文件: {path}")

    def test_alembic_ini_points_to_migrations_directory(self):
        parser = configparser.ConfigParser()
        parser.read(ROOT / "alembic.ini", encoding="utf-8")

        self.assertEqual(parser.get("alembic", "script_location"), "migrations")
        self.assertEqual(parser.get("alembic", "prepend_sys_path"), ".")


if __name__ == "__main__":
    unittest.main()
