"""脚本沙箱一键验收：在真实沙箱容器里跑一遍隔离和依赖检查，替代 deployment.md 里手敲的命令。

用法（服务器上，进 api 容器里跑——它已经有 SANDBOX_URL / SANDBOX_TOKEN，也在能访问网关的网络里）：

    docker compose -f docker-compose.prod.yml exec api python scripts/sandbox_acceptance.py

    --url / --token   指定别的沙箱地址（默认读环境变量 SANDBOX_URL / SANDBOX_TOKEN）
    --only a,b        只跑指定检查（名字见下面输出的第一列）
    --skip-heavy      跳过会占大量内存的检查（本机没有隔离时不要跑）

退出码：0 = 没有 FAIL；1 = 有 FAIL；2 = 沙箱没开启/连不上。任何"隔离"类的 FAIL，请立刻关掉沙箱（SANDBOX_ENABLED=false）。

它执行的都是本脚本里写死的几行测试代码，用来确认：网络出不去、连不到内部服务、文件系统只读、超时会被杀、
内存有上限、非 root、环境里没有业务密钥，以及镜像里声明装了的库真的能 import。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from service.sandbox import RunnerBackend, SandboxUnavailable  # noqa: E402
from service.skills_core.script_report import SANDBOX_MODULES  # noqa: E402

PASS, FAIL, INFO = "PASS", "FAIL", "INFO"

CONNECT_PROBE = """
import json, socket
targets = {targets}
out = {{}}
for name, (host, port) in targets.items():
    try:
        socket.create_connection((host, port), timeout=3).close()
        out[name] = "connected"
    except Exception as e:
        out[name] = "failed:" + type(e).__name__
print(json.dumps(out))
"""


def _json(res):
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return None


class Acceptance:
    def __init__(self, url: str, token: str):
        self.url, self.token = url, token
        self.backend = RunnerBackend(url, token)

    def run(self, code: str, timeout: int = 10, files=None):
        payload = {"main.py": code.encode()}
        payload.update(files or {})
        return self.backend.run(payload, "main.py", [], timeout)

    # ---- 检查项：返回 (状态, 说明) ----

    def health(self):
        r = requests.get(self.url.rstrip("/") + "/health", timeout=5)
        return (PASS, "沙箱网关/沙箱健康") if r.status_code == 200 else (FAIL, f"/health 返回 {r.status_code}")

    def basic_run(self):
        r = self.run("print('hello-sandbox')")
        ok = r.exit_code == 0 and "hello-sandbox" in r.stdout
        return (PASS, f"能运行脚本，用时 {r.duration}s") if ok else (FAIL, f"exit={r.exit_code} stderr={r.stderr[-200:]}")

    def non_root(self):
        r = self.run("import os\nprint(os.getuid() if hasattr(os, 'getuid') else -1)")
        uid = r.stdout.strip()
        if uid == "-1":
            return INFO, "当前系统没有 uid（不是 Linux 容器？）"
        return (PASS, f"以非 root 运行（uid={uid}）") if uid not in ("0", "") else (FAIL, "脚本以 root 运行")

    def no_egress(self):
        r = self.run(CONNECT_PROBE.format(targets=repr({
            "cloudflare-dns": ("1.1.1.1", 53), "google-dns": ("8.8.8.8", 53), "aliyun-dns": ("223.5.5.5", 53),
        })) + "\nimport socket as s\ntry:\n    s.getaddrinfo('example.com', 80)\n    print(json.dumps({'dns-resolve': 'resolved'}))\nexcept Exception:\n    print(json.dumps({'dns-resolve': 'failed'}))\n", timeout=20)
        lines = [json.loads(x) for x in r.stdout.strip().splitlines() if x.startswith("{")]
        merged = {k: v for d in lines for k, v in d.items()}
        leaked = [k for k, v in merged.items() if v in ("connected", "resolved")]
        return (FAIL, f"能连出外网：{leaked}") if leaked else (PASS, "连不出外网，也解析不了外部域名")

    def no_internal_access(self):
        targets = {"db": ("db", 3306), "redis": ("redis", 6379), "chroma": ("chroma", 8000),
                   "api": ("api", 8000), "worker": ("worker", 8000)}
        r = self.run(CONNECT_PROBE.format(targets=repr(targets)), timeout=20)
        res = _json(r) or {}
        reached = [k for k, v in res.items() if v == "connected"]
        return (FAIL, f"能连到内部服务：{reached}") if reached else (PASS, "连不到 db / redis / chroma / api / worker")

    def readonly_fs(self):
        code = """
import json
out = {}
for name, path in {"runner-dir": "/opt/runner/x", "etc": "/etc/x", "usr": "/usr/x"}.items():
    try:
        open(path, "w").write("x"); out[name] = "writable"
    except Exception:
        out[name] = "blocked"
try:
    open("scratch.txt", "w").write("x"); out["workdir"] = "writable"
except Exception:
    out["workdir"] = "blocked"
print(json.dumps(out))
"""
        res = _json(self.run(code)) or {}
        bad = [k for k in ("runner-dir", "etc", "usr") if res.get(k) == "writable"]
        if bad:
            return FAIL, f"这些位置可写：{bad}（根文件系统不是只读）"
        return (PASS, "根文件系统只读，工作目录可写") if res.get("workdir") == "writable" else (FAIL, "工作目录不可写，脚本没法产出文件")

    def outputs_returned(self):
        r = self.run("import os\nos.makedirs('outputs', exist_ok=True)\nopen('outputs/a.txt','w').write('hi')\nprint('done')")
        got = {p: c for p, c in r.outputs}
        return (PASS, "生成的文件能带回来") if got.get("outputs/a.txt") == b"hi" else (FAIL, f"产出文件没带回来：{list(got)}")

    def timeout_kills(self):
        started = time.time()
        r = self.run("while True:\n    pass", timeout=3)
        took = time.time() - started
        return (PASS, f"死循环在 {took:.1f}s 被终止") if r.timed_out and took < 12 else (FAIL, f"没被及时终止：timed_out={r.timed_out} 用时 {took:.1f}s")

    def memory_limit(self):
        r = self.run("x = bytearray(1500 * 1024 * 1024)\nprint('allocated')", timeout=20)
        return (FAIL, "分配 1.5GB 成功，内存上限没生效") if "allocated" in r.stdout else (PASS, "超过内存上限的脚本被拒绝/终止")

    def env_clean(self):
        r = self.run("import os, json\nprint(json.dumps(sorted(os.environ)))")
        names = _json(r) or []
        risky = [n for n in names if any(w in n.upper() for w in ("PASSWORD", "SECRET", "JWT", "DB_", "API_KEY", "ACCESS_KEY"))]
        return (FAIL, f"脚本环境里有疑似密钥：{risky}") if risky else (PASS, f"脚本环境很干净（{len(names)} 个变量）")

    def token_visibility(self):
        r = self.run("try:\n    print('SANDBOX_TOKEN' in open('/proc/1/environ', errors='ignore').read())\nexcept Exception:\n    print('unreadable')")
        seen = r.stdout.strip()
        if seen == "True":
            return INFO, "脚本能读到沙箱自己的令牌（已知限制：令牌只能调用沙箱，且网关只通向沙箱，价值有限）"
        return INFO, "脚本读不到沙箱令牌"

    def libs_import(self):
        mods = sorted(SANDBOX_MODULES)
        code = ("import importlib, json\nfailed = {}\nfor m in %r:\n    try:\n        importlib.import_module(m)\n"
                "    except Exception as e:\n        failed[m] = type(e).__name__\nprint(json.dumps(failed))\n") % (mods,)
        res = _json(self.run(code, timeout=45))
        if res is None:
            return FAIL, "依赖检查脚本没有正常输出"
        return (PASS, f"声明装了的 {len(mods)} 个模块都能 import") if not res else (FAIL, f"这些模块声明了但 import 失败：{res}")

    def ffmpeg(self):
        r = self.run("import shutil, subprocess\np = shutil.which('ffmpeg')\nprint(p)\nif p:\n    print(subprocess.run([p, '-version'], capture_output=True, text=True).stdout.splitlines()[0])")
        return (PASS, r.stdout.strip().splitlines()[-1]) if "ffmpeg version" in r.stdout else (FAIL, "找不到可用的 ffmpeg（依赖它的脚本会失败）")

    CHECKS = [
        ("health", "沙箱健康", health, False),
        ("basic_run", "能运行脚本", basic_run, False),
        ("non_root", "非 root 运行", non_root, False),
        ("no_egress", "连不出外网", no_egress, False),
        ("no_internal_access", "连不到内部服务", no_internal_access, False),
        ("readonly_fs", "文件系统只读", readonly_fs, False),
        ("env_clean", "环境无业务密钥", env_clean, False),
        ("timeout_kills", "超时会被终止", timeout_kills, False),
        ("memory_limit", "内存有上限", memory_limit, True),
        ("outputs_returned", "产出文件能带回", outputs_returned, False),
        ("libs_import", "声明的依赖都能 import", libs_import, False),
        ("ffmpeg", "ffmpeg 可用", ffmpeg, False),
        ("token_visibility", "沙箱令牌可见性（信息）", token_visibility, False),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.getenv("SANDBOX_URL", "http://sandbox-gw:8090"))
    ap.add_argument("--token", default=os.getenv("SANDBOX_TOKEN", ""))
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-heavy", action="store_true")
    args = ap.parse_args()

    if not args.token:
        print("没有 SANDBOX_TOKEN：沙箱没开启，或者不是在 api 容器里运行（用 --token 指定）")
        return 2
    acc = Acceptance(args.url, args.token)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    results = []
    print(f"沙箱地址：{args.url}\n")
    for name, title, fn, heavy in Acceptance.CHECKS:
        if (only and name not in only) or (heavy and args.skip_heavy):
            continue
        try:
            status, msg = fn(acc)
        except SandboxUnavailable as e:
            print(f"沙箱连不上：{e}")
            return 2
        except Exception as e:  # noqa: BLE001
            status, msg = FAIL, f"检查本身出错：{type(e).__name__}: {e}"
        results.append((name, status))
        print(f"[{status}] {name:20} {title}：{msg}")

    fails = [n for n, s in results if s == FAIL]
    print(f"\n共 {len(results)} 项：通过 {sum(s == PASS for _, s in results)}，失败 {len(fails)}，信息 {sum(s == INFO for _, s in results)}")
    if fails:
        print("有失败项：" + ", ".join(fails))
        print("涉及隔离的失败（no_egress / no_internal_access / readonly_fs / env_clean）请立刻关闭沙箱：SANDBOX_ENABLED=false")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
