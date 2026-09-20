"""Skill 脚本沙箱运行器。

只做一件事：把主服务发来的文件写进临时目录，跑其中一个 Python 脚本，把 stdout 和新生成的文件带回去。

隔离主要靠容器本身（docker-compose.prod.yml 里：无外网的内部网络、只读根文件系统、非 root、
丢弃全部 capability、CPU/内存/进程数上限）。这里再叠两层：进程级 rlimit 和硬超时。
本服务不持有任何业务密钥，没有数据库/Redis 连接，被攻破也拿不到东西。
"""
import base64
import hmac
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import List

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

TOKEN = os.environ.get("SANDBOX_TOKEN", "")
if not TOKEN:
    raise SystemExit("SANDBOX_TOKEN 未设置，拒绝启动（没有令牌任何人都能在这里跑代码）")

MAX_CONCURRENT = int(os.environ.get("SANDBOX_MAX_CONCURRENT", "2"))
MAX_TIMEOUT = int(os.environ.get("SANDBOX_MAX_TIMEOUT", "60"))
MAX_INPUT_BYTES = 60 * 1024 * 1024
MAX_INPUT_FILES = 1500
MAX_OUTPUT_FILES = 20
MAX_OUTPUT_FILE_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_TOTAL_BYTES = 20 * 1024 * 1024
MAX_STREAM_BYTES = 50_000
MEMORY_LIMIT_BYTES = int(os.environ.get("SANDBOX_MEMORY_BYTES", str(1024 * 1024 * 1024)))
WORK_ROOT = "/work" if os.path.isdir("/work") else None

app = FastAPI(title="skill-sandbox", docs_url=None, redoc_url=None, openapi_url=None)
_slots = threading.Semaphore(MAX_CONCURRENT)


class FileItem(BaseModel):
    path: str = Field(max_length=300)
    b64: str


class RunRequest(BaseModel):
    files: List[FileItem]
    script: str = Field(max_length=300)
    args: List[str] = Field(default_factory=list, max_length=30)
    timeout: int = Field(default=30, ge=1)


def _safe_rel(path: str) -> str:
    p = path.replace("\\", "/")
    if not p or p.startswith("/") or ".." in p.split("/") or "\x00" in p or (len(p) > 1 and p[1] == ":"):
        raise HTTPException(400, f"非法路径: {path!r}")
    return p


def _limits():
    """子进程启动前设置资源上限（仅 Linux）。"""
    import resource

    def apply():
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_FILE_BYTES * 2, MAX_OUTPUT_FILE_BYTES * 2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return apply


def _snapshot(root: str) -> dict:
    snap = {}
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in names:
            full = os.path.join(base, n)
            try:
                st = os.stat(full)
            except OSError:
                continue
            snap[os.path.relpath(full, root).replace("\\", "/")] = (st.st_size, st.st_mtime_ns)
    return snap


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/run")
def run(req: RunRequest, x_sandbox_token: str = Header(default="")):
    if not hmac.compare_digest(x_sandbox_token, TOKEN):
        raise HTTPException(401, "invalid token")
    if len(req.files) > MAX_INPUT_FILES:
        raise HTTPException(400, "文件数量过多")
    script = _safe_rel(req.script)
    if not script.endswith(".py"):
        raise HTTPException(400, "只能运行 .py 脚本")
    timeout = min(req.timeout, MAX_TIMEOUT)

    if not _slots.acquire(timeout=5):
        raise HTTPException(503, "沙箱正忙，请稍后重试")
    workdir = tempfile.mkdtemp(prefix="run_", dir=WORK_ROOT)
    try:
        total = 0
        paths = set()
        for item in req.files:
            rel = _safe_rel(item.path)
            data = base64.b64decode(item.b64)
            total += len(data)
            if total > MAX_INPUT_BYTES:
                raise HTTPException(413, "输入文件总体积过大")
            target = os.path.join(workdir, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
            paths.add(rel)
        if script not in paths:
            raise HTTPException(400, f"脚本不在上传的文件里: {script}")

        before = _snapshot(workdir)
        home = os.path.join(workdir, ".home")
        os.makedirs(home, exist_ok=True)
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": home,
            "TMPDIR": home,
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLBACKEND": "Agg",
        }
        if os.name == "nt":  # 仅本地开发调试：Windows 下 Python 需要 SYSTEMROOT
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
        kwargs = {"preexec_fn": _limits(), "start_new_session": True} if os.name == "posix" else {}

        started = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, script, *req.args],
            cwd=workdir, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs,
        )
        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill(proc)
            out, err = proc.communicate()
        duration = round(time.monotonic() - started, 2)

        after = _snapshot(workdir)
        outputs, out_total, truncated = [], 0, False
        for rel, meta in sorted(after.items()):
            if rel.startswith(".home/") or rel.endswith(".pyc") or before.get(rel) == meta:
                continue
            if len(outputs) >= MAX_OUTPUT_FILES or meta[0] > MAX_OUTPUT_FILE_BYTES or out_total + meta[0] > MAX_OUTPUT_TOTAL_BYTES:
                truncated = True
                continue
            with open(os.path.join(workdir, *rel.split("/")), "rb") as f:
                data = f.read()
            out_total += len(data)
            outputs.append({"path": rel, "b64": base64.b64encode(data).decode()})

        return {
            "exit_code": -1 if timed_out else proc.returncode,
            "timed_out": timed_out,
            "duration": duration,
            "stdout": out[:MAX_STREAM_BYTES].decode("utf-8", "replace"),
            "stderr": err[-MAX_STREAM_BYTES:].decode("utf-8", "replace"),
            "outputs": outputs,
            "truncated": truncated,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        _slots.release()


def _kill(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        pass
