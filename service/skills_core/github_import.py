"""从 GitHub 链接导入 Skill：只下载公开仓库的 zip，再交给 package_import 处理。

安全：下载地址由我们自己拼成 https://codeload.github.com/<owner>/<repo>/zip/<ref>，
owner / repo / ref 都过正则白名单，用户给的链接只用来"取参数"，不会被当成请求地址，
所以不会被拿去探测内网（SSRF）。
"""
import re
from typing import Any, Dict, Tuple

import requests

from .package_import import MAX_UPLOAD_BYTES, SkillImportError, import_skill_bundle

_URL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/(?:tree|blob)/([A-Za-z0-9_.-]+)(?:/(.*?))?)?/?$"
)
_HINT = "也可以在自己电脑上打开该链接，点绿色的 Code 按钮 → Download ZIP，再用「上传文件」导入。"


def parse_github_url(url: str) -> Tuple[str, str, str, str]:
    """返回 (owner, repo, ref, subpath)。ref 缺省为 HEAD（仓库默认分支）。"""
    m = _URL_RE.match((url or "").strip())
    if not m:
        raise SkillImportError(
            "链接格式不对。请粘贴 GitHub 仓库或文件夹的地址，例如 "
            "https://github.com/anthropics/skills 或 https://github.com/anthropics/skills/tree/main/skills/pdf"
        )
    owner, repo, ref, sub = m.group(1), m.group(2), m.group(3) or "HEAD", (m.group(4) or "").strip("/")
    if sub.lower().endswith("skill.md"):  # 指向 SKILL.md 文件时，取它所在的文件夹
        sub = sub.rsplit("/", 1)[0] if "/" in sub else ""
    if ".." in sub.split("/"):
        raise SkillImportError("链接里的路径不合法")
    return owner, repo, ref, sub


def download_repo_zip(owner: str, repo: str, ref: str) -> bytes:
    url = f"https://codeload.github.com/{owner}/{repo}/zip/{ref}"
    try:
        resp = requests.get(url, stream=True, timeout=(8, 30), allow_redirects=False)
        if 300 <= resp.status_code < 400:
            loc = resp.headers.get("Location", "")
            if not loc.startswith("https://codeload.github.com/"):
                raise SkillImportError("GitHub 返回了意外的跳转，已拒绝")
            resp = requests.get(loc, stream=True, timeout=(8, 30), allow_redirects=False)
        if resp.status_code == 404:
            raise SkillImportError("找不到这个仓库或分支。只支持公开仓库，请检查链接是否拼写正确")
        if resp.status_code != 200:
            raise SkillImportError(f"GitHub 返回了 {resp.status_code}，请稍后重试。{_HINT}")
        chunks, size = [], 0
        for chunk in resp.iter_content(chunk_size=256 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise SkillImportError("这个仓库太大了（超过 50MB）。请链接到具体的 Skill 文件夹，或自己下载后只打包需要的部分")
            chunks.append(chunk)
        return b"".join(chunks)
    except (requests.ConnectionError, requests.Timeout):
        raise SkillImportError(f"服务器暂时访问不到 GitHub（国内网络常见）。{_HINT}")


def import_from_github(db, user_id: int, url: str, is_public: int = 0, allow_scripts: bool = True) -> Dict[str, Any]:
    owner, repo, ref, sub = parse_github_url(url)
    content = download_repo_zip(owner, repo, ref)
    return import_skill_bundle(
        db, user_id, filename=f"{repo}.zip", content=content, is_public=is_public, subpath=sub,
        allow_scripts=allow_scripts,
    )
