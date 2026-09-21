"""atomic_write_validated：先写同目录临时文件并校验，通过后才原子替换正式配置。"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml

import service.tools  # noqa: F401
from service.skills import loader as skill_loader
from service.skills_core import config_io


def _config(prompt: str) -> str:
    return yaml.safe_dump(
        {"name": "演示", "description": "d", "tools": [{"name": "word_count", "defaults": {}}], "system_prompt": prompt},
        allow_unicode=True, sort_keys=False,
    )


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cfgio_")
        os.makedirs(os.path.join(self.root, "user_created"))
        self.rel = "user_created/demo.yml"
        self.path = os.path.join(self.root, self.rel)
        self._patch = patch.object(skill_loader, "SKILLS_ROOT", self.root)
        self._patch.start()
        skill_loader.invalidate_skill_config()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)
        skill_loader.invalidate_skill_config()

    def temp_files(self):
        return [n for n in os.listdir(os.path.dirname(self.path)) if n.startswith(".skill-")]

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_valid_content_replaces_the_file_and_leaves_no_temp(self):
        result = config_io.atomic_write_validated(self.rel, _config("新内容"))
        self.assertTrue(result["ok"])
        self.assertIn("新内容", self.read())
        self.assertEqual(self.temp_files(), [])
        self.assertEqual(skill_loader.load_skill_config(self.rel)["system_prompt"], "新内容")

    def test_invalid_content_keeps_the_original(self):
        config_io.atomic_write_validated(self.rel, _config("原内容"))
        bad = yaml.safe_dump({"name": "x", "tools": [{"name": "no_such_tool"}], "system_prompt": "坏"})
        result = config_io.atomic_write_validated(self.rel, bad)
        self.assertFalse(result["ok"])
        self.assertIn("原内容", self.read())
        self.assertEqual(self.temp_files(), [])

    def test_failed_replace_cleans_up_the_temp_file(self):
        config_io.atomic_write_validated(self.rel, _config("原内容"))
        with patch.object(config_io.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                config_io.atomic_write_validated(self.rel, _config("新内容"))
        self.assertIn("原内容", self.read())
        self.assertEqual(self.temp_files(), [])

    def test_path_outside_the_skills_root_is_refused(self):
        with self.assertRaises(Exception):
            config_io.atomic_write_validated("../escape.yml", _config("x"))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.root), "escape.yml")))

    @unittest.skipIf(os.name == "nt", "POSIX 权限位")
    def test_published_file_is_world_readable(self):
        config_io.atomic_write_validated(self.rel, _config("x"))
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
