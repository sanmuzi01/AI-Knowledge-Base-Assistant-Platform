"""Atomic writes for live Skill configuration files."""
import os
import tempfile
from typing import Dict

from service.skills import loader as skill_loader

from .validation import validate_skill_config_file


def atomic_write_validated(config_file: str, content: str) -> Dict:
    """Validate a sibling temporary file, then atomically publish it."""
    config_path = skill_loader._get_yml_path(config_file)
    directory = os.path.dirname(config_path)
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".skill-", suffix=".yml", dir=directory)
    temp_file = os.path.relpath(temp_path, skill_loader.SKILLS_ROOT).replace("\\", "/")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o644)   # mkstemp 默认 0600，容器里以别的用户读取会失败
        skill_loader.invalidate_skill_config(temp_file)
        validation = validate_skill_config_file(temp_file)
        if not validation["ok"]:
            return validation
        os.replace(temp_path, config_path)
        skill_loader.invalidate_skill_config(config_file)
        return validation
    finally:
        skill_loader.invalidate_skill_config(temp_file)
        if os.path.exists(temp_path):
            os.remove(temp_path)
