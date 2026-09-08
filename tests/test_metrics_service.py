import unittest

from service.metrics_service import normalize_metric_path


class MetricsServiceTest(unittest.TestCase):
    def test_normalize_numeric_path_parts(self):
        self.assertEqual(normalize_metric_path("/task/123/retry"), "/task/{id}/retry")
        self.assertEqual(normalize_metric_path("/knowledge/9/88/chunks"), "/knowledge/{id}/{id}/chunks")

    def test_normalize_long_token_path_parts(self):
        path = "/download/abc1234567890abc1234567890abc1234567890"
        self.assertEqual(normalize_metric_path(path), "/download/{token}")


if __name__ == "__main__":
    unittest.main()
