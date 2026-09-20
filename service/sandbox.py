"""脚本沙箱客户端。

主服务自己不执行任何 Skill 脚本：把脚本和输入文件发给独立的沙箱容器（sandbox/runner.py），
拿回输出。后端做成可替换的——以后想换成云上的沙箱服务，实现 SandboxBackend 并改 get_backend() 即可，
调用方（service/tools/skill_script.py）不用动。

默认关闭：SANDBOX_ENABLED=true 且 SANDBOX_TOKEN 已设置才生效。
"""
import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests


class SandboxUnavailable(RuntimeError):
    """沙箱没开、连不上或正忙。message 可以直接给用户/模型看。"""


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration: float = 0.0
    truncated: bool = False
    outputs: List[Tuple[str, bytes]] = field(default_factory=list)


class SandboxBackend(ABC):
    @abstractmethod
    def run(self, files: Dict[str, bytes], script: str, args: List[str], timeout: int) -> SandboxResult:
        """files: 相对路径 → 内容，会原样铺进沙箱工作目录；script 是其中一个 .py 的相对路径。"""


class RunnerBackend(SandboxBackend):
    """通过 HTTP 调用 docker-compose 里的 sandbox 服务。"""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def run(self, files: Dict[str, bytes], script: str, args: List[str], timeout: int) -> SandboxResult:
        payload = {
            "files": [{"path": p, "b64": base64.b64encode(c).decode()} for p, c in files.items()],
            "script": script,
            "args": args,
            "timeout": timeout,
        }
        try:
            resp = requests.post(
                f"{self.url}/run", json=payload, headers={"X-Sandbox-Token": self.token},
                timeout=(3, timeout + 15),
            )
        except requests.RequestException:
            raise SandboxUnavailable("脚本沙箱暂时连不上，请稍后重试或联系管理员")
        if resp.status_code == 503:
            raise SandboxUnavailable("脚本沙箱正忙，请稍后重试")
        if resp.status_code != 200:
            detail = ""
            try:
                detail = str(resp.json().get("detail", ""))
            except ValueError:
                pass
            raise SandboxUnavailable(f"脚本沙箱拒绝了这次运行（{resp.status_code}）：{detail[:200]}")
        data = resp.json()
        return SandboxResult(
            exit_code=int(data["exit_code"]),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            timed_out=bool(data.get("timed_out")),
            duration=float(data.get("duration", 0)),
            truncated=bool(data.get("truncated")),
            outputs=[(o["path"], base64.b64decode(o["b64"])) for o in data.get("outputs", [])],
        )


def is_enabled() -> bool:
    flag = os.getenv("SANDBOX_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return flag and bool(os.getenv("SANDBOX_TOKEN", "").strip())


def get_backend() -> Optional[SandboxBackend]:
    if not is_enabled():
        return None
    return RunnerBackend(os.getenv("SANDBOX_URL", "http://sandbox:8090"), os.environ["SANDBOX_TOKEN"].strip())


def default_timeout() -> int:
    try:
        return max(1, min(int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30")), 60))
    except ValueError:
        return 30
