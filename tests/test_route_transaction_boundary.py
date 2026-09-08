import pathlib
import unittest


class RouteTransactionBoundaryTest(unittest.TestCase):
    def test_routes_do_not_commit_transactions(self):
        """路由层不能直接提交事务，写操作必须下沉到 service 层。"""
        api_dir = pathlib.Path(__file__).resolve().parents[1] / "FasdtApi"
        offenders = []
        for path in api_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "db.commit(" in text:
                offenders.append(path.name)
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
