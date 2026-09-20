"""运行 Skill 自带的 Python 脚本。

脚本不在主服务里执行：文件被发到隔离的沙箱容器（service/sandbox.py），这里只负责
打包 Skill 文件和用户附件、调用沙箱、把输出和生成的文件交回给模型。

这个工具不写在 Skill 的 tools 列表里：只有沙箱开启、且 Agent 绑定的 Skill 带脚本时，
service/skills_core/binding.py 才会把它加进去。
"""
import os
from typing import Dict, List, Tuple

from service import attachment_service, sandbox
from service.tools.base import BaseTool, ToolRegistry

MAX_BUNDLE_BYTES = 30 * 1024 * 1024
MAX_BUNDLE_FILES = 1500
MAX_STDOUT_CHARS = 6000
MAX_STDERR_CHARS = 3000


def _collect_bundle(root: str) -> Tuple[Dict[str, bytes], str]:
    files: Dict[str, bytes] = {}
    total = 0
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in names:
            full = os.path.join(base, n)
            rel = os.path.relpath(full, root).replace("\\", "/")
            with open(full, "rb") as f:
                data = f.read()
            total += len(data)
            files[rel] = data
            if total > MAX_BUNDLE_BYTES or len(files) > MAX_BUNDLE_FILES:
                return {}, "这个 Skill 的文件太大，无法送进沙箱"
    return files, ""


@ToolRegistry.register
class RunSkillScriptTool(BaseTool):
    requires_context = True

    def get_name(self) -> str:
        return "run_skill_script"

    def get_description(self) -> str:
        return (
            "运行已安装 Skill 自带的 Python 脚本（在隔离沙箱里执行，无网络）。"
            "当 Skill 说明里让你运行 scripts/xxx.py 时调用它，不要自己假装运行过。"
            "skill 填 Skill 名称；script 填脚本相对路径，如 scripts/extract.py；"
            "args 是命令行参数列表；input_files 填用户上传的附件 ID，文件会出现在沙箱的 inputs/ 目录下，"
            "args 里用 inputs/文件名 引用。脚本生成的文件请写到 outputs/ 目录，工具会返回下载链接。"
        )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "Skill 名称（只有一个带脚本的 Skill 时可省略）"},
                "script": {"type": "string", "description": "脚本相对路径，如 scripts/extract.py"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "命令行参数列表"},
                "input_files": {"type": "array", "items": {"type": "string"}, "description": "用户附件 ID 列表"},
            },
            "required": ["script"],
        }

    def execute(self, **kwargs) -> str:
        ctx = self._ctx
        backend = sandbox.get_backend()
        if backend is None:
            return "脚本沙箱未开启，无法运行脚本。请直接用文字完成任务，并告诉用户这一步需要管理员开启脚本沙箱。"
        if ctx is None or not ctx.user_id:
            return "缺少用户上下文，无法运行脚本。"

        bundles: Dict[str, dict] = getattr(ctx, "skill_bundles", None) or {}
        skill = str(kwargs.get("skill") or "").strip()
        if skill:
            match = next((b for n, b in bundles.items() if n == skill or n.lower() == skill.lower()), None)
            if match is None:
                return f"没有找到带脚本的 Skill「{skill}」。可用：{', '.join(bundles) or '无'}"
        elif len(bundles) == 1:
            match = next(iter(bundles.values()))
        else:
            return f"有多个带脚本的 Skill，请用 skill 参数指定：{', '.join(bundles) or '无'}"

        script = str(kwargs.get("script") or "").replace("\\", "/").lstrip("./")
        if script not in match["scripts"]:
            listed = "、".join(match["scripts"][:20])
            return f"这个 Skill 里没有脚本 {script}。可运行的脚本：{listed}"

        files, err = _collect_bundle(match["root"])
        if err:
            return err

        used_names = set()
        for att_id in list(kwargs.get("input_files") or [])[: attachment_service.MAX_ATTACHMENTS_PER_MESSAGE]:
            found = attachment_service.resolve(ctx.user_id, str(att_id))
            if not found:
                return f"找不到附件 {att_id}（可能已过期，请让用户重新上传）"
            path, name = found
            if name in used_names:
                name = f"{att_id[:6]}_{name}"
            used_names.add(name)
            files[f"inputs/{name}"] = path.read_bytes()

        args: List[str] = [str(a) for a in (kwargs.get("args") or [])][:30]
        try:
            result = backend.run(files, script, args, sandbox.default_timeout())
        except sandbox.SandboxUnavailable as e:
            return str(e)

        lines = []
        if result.timed_out:
            lines.append(f"运行超时（超过 {sandbox.default_timeout()} 秒）被终止。")
        else:
            lines.append(f"运行结束，退出码 {result.exit_code}，用时 {result.duration} 秒。")
        if result.stdout.strip():
            lines.append("标准输出：\n" + result.stdout[:MAX_STDOUT_CHARS])
        if (result.exit_code != 0 or result.timed_out) and result.stderr.strip():
            lines.append("错误输出：\n" + result.stderr[-MAX_STDERR_CHARS:])

        saved = []
        for rel, data in result.outputs:
            try:
                saved.append(attachment_service.save(ctx.user_id, os.path.basename(rel), data, check_ext=False))
            except attachment_service.AttachmentError:
                continue
        if saved:
            lines.append(
                "生成的文件（回答时请原样使用这些链接格式交给用户）：\n"
                + "\n".join(f"- [{s['name']}](attachment://{s['id']})" for s in saved)
            )
        if result.truncated:
            lines.append("注意：生成的文件过多或过大，部分文件没有返回。")
        return "\n\n".join(lines)
