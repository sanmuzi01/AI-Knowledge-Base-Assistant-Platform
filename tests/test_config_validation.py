import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

from service.config_validation import assert_runtime_config, validate_runtime_config


def _valid_env():
    return {
        "APP_ENV": "production",
        "DB_USER": "root",
        "DB_PASSWORD": "strong-password",
        "DB_HOST": "mysql",
        "DB_PORT": "3306",
        "DB_NAME": "agent_sql",
        "JWT_SECRET_KEY": "strong-jwt-secret-value-for-production",
        "LLM_ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
        "REDIS_URL": "redis://redis:6379/0",
        "SMS_PROVIDER": "webhook",
        "SMS_WEBHOOK_URL": "https://sms.example.test/send",
        "SMS_WEBHOOK_TOKEN": "strong-sms-token",
        "SMS_EXPOSE_DEV_CODE": "0",
        "TRUSTED_HOSTS": "example.test,www.example.test,api",
        "CORS_ALLOW_ORIGINS": "https://example.test,https://www.example.test",
        "GRAFANA_ADMIN_PASSWORD": "strong-grafana-password",
    }


class ConfigValidationTest(unittest.TestCase):
    def test_production_config_accepts_valid_values(self):
        with patch.dict(os.environ, _valid_env(), clear=True):
            result = validate_runtime_config()
            self.assertTrue(result["ok"])
            self.assertEqual(result["environment"], "production")
            assert_runtime_config()

    def test_production_config_rejects_placeholders(self):
        env = _valid_env()
        env["JWT_SECRET_KEY"] = "change-me-random-64-hex-or-long-secret"
        with patch.dict(os.environ, env, clear=True):
            result = validate_runtime_config()
            self.assertFalse(result["ok"])
            with self.assertRaises(RuntimeError):
                assert_runtime_config()

    def test_development_config_allows_missing_redis(self):
        env = _valid_env()
        env["APP_ENV"] = "development"
        env["REDIS_URL"] = ""
        with patch.dict(os.environ, env, clear=True):
            result = validate_runtime_config()
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["warning_count"], 1)


if __name__ == "__main__":
    unittest.main()
