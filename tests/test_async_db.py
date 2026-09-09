import unittest

from models import async_db


class AsyncDatabaseConfigTestCase(unittest.TestCase):
    def test_async_database_url_uses_asyncmy_driver(self):
        self.assertIn("mysql+asyncmy://", async_db.ASYNC_DATABASE_URL)

    def test_async_session_dependency_is_required(self):
        self.assertTrue(async_db.async_database_available())
        self.assertIsNotNone(async_db.AsyncSessionLocal)
        self.assertTrue(callable(async_db.get_async_db))


if __name__ == "__main__":
    unittest.main()
