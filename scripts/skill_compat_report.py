"""生成 Skill 预制包的脚本兼容性清单（Markdown）。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe scripts/skill_compat_report.py skill-packs/anbeime-skills-all.zip -o skill-packs/COMPATIBILITY.md

只读 zip 里的源码做静态检查（和导入时用的是同一套逻辑：service/skills_core/script_report.py），
不执行任何脚本，也不需要数据库和服务在运行。
往沙箱里加了依赖（sandbox/requirements.txt + script_report.PACKAGE_MODULES）之后重新跑一遍，
提交前后的差异就是"这次加依赖多解锁了哪些 Skill"。
"""
import argparse
import os
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.skills_core import script_report as sr  # noqa: E402
from service.skills_core.package_import import _find_roots, _norm, _owner_root, parse_skill_md  # noqa: E402

# 卡住的库归到哪一类——这决定了"要解锁它得做什么"（见 docs/skill-extension.md 第 3 节）
CATEGORIES = {
    "需要联网": {"requests", "httpx", "aiohttp", "edge_tts", "openai", "anthropic", "dashscope", "zhipuai",
                 "langchain_openai", "langchain_core"},
    "平台专属 SDK": {"coze_workload_identity"},
    "深度学习 / 模型权重": {"torch", "torchaudio", "transformers", "einops", "kokoro", "librosa", "numba",
                            "tensorflow", "wan"},
    "浏览器自动化": {"patchright", "playwright", "selenium", "browser_auth"},
    "已评估、暂未安装": {"moviepy"},  # 1.0.3 与新版 Pillow / NumPy 2 有已知不兼容，能实机验证后再装
    "系统组件 / 常驻服务": {"pyttsx3", "pdf2image", "flask", "flask_cors", "schedule"},
}
STATUS_ORDER = {"ready": 0, "partial": 1, "unsupported": 2, "none": 3}
STATUS_TEXT = {"ready": "全部可运行", "partial": "部分可运行", "unsupported": "暂不支持", "none": "纯说明（无脚本）"}


def category_of(module: str) -> str:
    for name, mods in CATEGORIES.items():
        if module in mods:
            return name
    return "仓库内部模块（Skill 没带全）"


def analyze_zip(zip_path: str):
    rows = []
    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory() as tmp:
        names = [n for n in (_norm(i.filename) for i in zf.infolist() if not i.is_dir())
                 if not n.startswith("/") and ".." not in n.split("/")]
        roots = _find_roots(names)
        for info in zf.infolist():
            n = _norm(info.filename)
            if info.is_dir() or n not in names:
                continue
            target = os.path.join(tmp, *n.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
        for root in roots:
            base = os.path.join(tmp, *root.split("/")) if root else tmp
            with open(os.path.join(base, "SKILL.md"), encoding="utf-8-sig", errors="replace") as f:
                meta, _ = parse_skill_md(f.read())
            own = [n for n in names if _owner_root(n, roots) == root]
            prefix = root + "/" if root else ""
            py = sorted(n[len(prefix):] for n in own if n.endswith(".py"))
            other = sum(1 for n in own if os.path.splitext(n)[1] in (".sh", ".js", ".mjs", ".ts"))
            rep = sr.analyze_bundle(base, py)
            rows.append({"name": str(meta.get("name") or os.path.basename(root)), "report": rep, "other_scripts": other})
    return rows


def render(rows, source: str) -> str:
    counts = Counter(r["report"]["status"] for r in rows)
    total_scripts = sum(r["report"]["total"] for r in rows)
    runnable = sum(len(r["report"]["runnable"]) for r in rows)
    out = [
        "# Skill 脚本兼容性清单",
        "",
        f"> 由 `scripts/skill_compat_report.py` 从 `{source}` 生成，**不要手改**。",
        "> 静态检查（只读源码）：判断的是「依赖是否齐、是否要联网」，不等于实测能跑——见 `docs/skill-extension.md` 第 6 节的验收清单。",
        "> 往沙箱加了依赖后重新生成，前后差异就是这次多解锁了哪些 Skill。",
        "",
        "## 概览",
        "",
        f"- Skill 共 {len(rows)} 个：" + "，".join(f"{STATUS_TEXT[s]} {counts.get(s, 0)}" for s in STATUS_ORDER),
        f"- 脚本共 {total_scripts} 个，静态检查通过 {runnable} 个",
        f"- 沙箱当前装了这些第三方模块：{', '.join(sorted(sr.SANDBOX_MODULES))}",
        "",
        "## 逐个 Skill",
        "",
        "| Skill | 状态 | 可运行 / 脚本数 | 缺少的依赖 | 联网脚本 | 调系统命令 | 非 Python 脚本（不能运行） |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (STATUS_ORDER[r["report"]["status"]], r["name"])):
        rep = r["report"]
        missing = "、".join(rep["missing_packages"][:6]) + ("…" if len(rep["missing_packages"]) > 6 else "")
        out.append(
            f"| {r['name']} | {STATUS_TEXT[rep['status']]} | {len(rep['runnable'])} / {rep['total']} | {missing or '-'} | "
            f"{rep['network'] or '-'} | {rep['system'] or '-'} | {r['other_scripts'] or '-'} |"
        )

    blockers = defaultdict(lambda: defaultdict(set))
    for r in rows:
        for m in r["report"]["missing_packages"]:
            blockers[category_of(m)][m].add(r["name"])
        if r["report"]["network"]:
            blockers["需要联网"]["（脚本里直接联网）"].add(r["name"])
    out += ["", "## 卡住的原因（按类别）", "", "| 类别 | 具体库 | 涉及的 Skill 数 |", "|---|---|---|"]
    for cat, mods in sorted(blockers.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
        detail = "、".join(f"{m}（{len(s)}）" for m, s in sorted(mods.items(), key=lambda kv: -len(kv[1])))
        out.append(f"| {cat} | {detail} | {len(set().union(*mods.values()))} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip_path")
    ap.add_argument("-o", "--out", help="输出的 Markdown 文件；不给就打印到屏幕")
    args = ap.parse_args()
    text = render(analyze_zip(args.zip_path), args.zip_path.replace("\\", "/"))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"已写入 {args.out}")
    else:
        print(text)
