"""service/feature_flags.py 的纯单元测试：不需要数据库，只测开关的读取语义。"""
import unittest
from unittest.mock import patch

from service import feature_flags


class UserApiConnectorsFlagTest(unittest.TestCase):
    def test_default_is_disabled(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("FEATURE_USER_API_CONNECTORS", None)
            self.assertFalse(feature_flags.user_api_connectors_enabled())

    def test_true_like_values_enable_it(self):
        for value in ("true", "1", "yes", "on", "TRUE", "  On  "):
            with patch.dict("os.environ", {"FEATURE_USER_API_CONNECTORS": value}):
                self.assertTrue(feature_flags.user_api_connectors_enabled(), value)

    def test_false_like_values_keep_it_disabled(self):
        for value in ("false", "0", "no", "off", "", "garbage"):
            with patch.dict("os.environ", {"FEATURE_USER_API_CONNECTORS": value}):
                self.assertFalse(feature_flags.user_api_connectors_enabled(), value)


if __name__ == "__main__":
    unittest.main()
