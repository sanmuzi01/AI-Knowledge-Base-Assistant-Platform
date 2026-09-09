"""守卫：service/widgets 包必须保持 100% 异步，不得泄漏同步 DB / 同步 HTTP。

允许的跨界方式只有一种：asyncio.to_thread 调用 RAG / 爬虫等同步子系统的入口
（rag_service.search_for_widget、web_crawler_service.crawl_url_to_markdown 等）。
"""

import pathlib
import re
import unittest

WIDGETS_DIR = pathlib.Path(__file__).resolve().parents[1] / "service" / "widgets"

# (正则, 说明)。命中即判定为同步泄漏。
FORBIDDEN = [
    (re.compile(r"\bSessionLocal\s*\("), "直接开同步 Session"),
    (re.compile(r"from\s+models\.init_db\s+import\s+.*SessionLocal"), "导入同步 SessionLocal"),
    (re.compile(r"\bget_db\b"), "依赖同步 get_db"),
    (re.compile(r"^\s*import\s+requests\b", re.M), "使用同步 requests"),
    (re.compile(r"\brequests\.(get|post|request|Session)\("), "使用同步 requests 调用"),
]


class SyncBoundaryTest(unittest.TestCase):
    def _py_files(self):
        return sorted(WIDGETS_DIR.rglob("*.py"))

    def test_no_sync_leak_in_widgets_package(self):
        offenders = []
        for path in self._py_files():
            text = path.read_text(encoding="utf-8")
            for rx, why in FORBIDDEN:
                if rx.search(text):
                    offenders.append(f"{path.relative_to(WIDGETS_DIR.parent.parent)} -> {why}")
        self.assertEqual(offenders, [], "service/widgets 出现同步泄漏：\n" + "\n".join(offenders))

    def test_every_connector_fetch_is_async(self):
        conn_dir = WIDGETS_DIR / "connectors"
        bad = []
        for path in conn_dir.glob("*.py"):
            if path.name in ("__init__.py", "base.py"):
                continue
            text = path.read_text(encoding="utf-8")
            if "def fetch(" in text and "async def fetch(" not in text:
                bad.append(path.name)
        self.assertEqual(bad, [])

    def test_knowledge_base_goes_through_rag_entrypoint(self):
        text = (WIDGETS_DIR / "connectors" / "knowledge_base.py").read_text(encoding="utf-8")
        self.assertIn("asyncio.to_thread", text)
        self.assertIn("search_for_widget", text)


if __name__ == "__main__":
    unittest.main()
