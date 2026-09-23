"""知识库能力扩展：Excel 解析 + 扫描件/图片 OCR 的回归测试。

- Excel 用真实 openpyxl 生成的 .xlsx 文件跑（不是 mock，openpyxl 本来就是项目依赖）。
- OCR 相关全部 mock `service.llm.vision_ocr`——真实调用视觉模型需要网络和真实 API Key，
  这里只验证"接线对不对"：没配视觉模型时的兜底行为、OCR 成功/失败时的行为、
  以及 MAX_OCR_PAGES_PER_DOCUMENT 上限生效。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from service.rag import rag_service


class ParseXlsxTest(unittest.TestCase):
    def _build_xlsx(self, path: str):
        from openpyxl import Workbook
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "价目表"
        ws1.append(["套餐", "价格"])
        ws1.append(["专业版", "39元/月"])
        wb.create_sheet("空表")  # 完全空白的第二个工作表
        wb.save(path)

    def test_sheet_rows_joined_with_pipe_and_sheet_name_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "sample.xlsx")
            self._build_xlsx(path)
            result = rag_service._parse_xlsx(path)

        self.assertIn("【价目表】", result)
        self.assertIn("套餐 | 价格", result)
        self.assertIn("专业版 | 39元/月", result)

    def test_empty_sheet_produces_no_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "sample.xlsx")
            self._build_xlsx(path)
            result = rag_service._parse_xlsx(path)

        self.assertNotIn("【空表】", result)


class ParseImageOcrTest(unittest.TestCase):
    def _tmp_png(self, tmp) -> str:
        path = str(Path(tmp) / "sample.png")
        # 最小合法 PNG 字节（1x1 像素），内容不重要——OCR 调用本身被 mock 掉了
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000a49444154789c6360000002000155e621bb00000000"
            "49454e44ae426082"
        )
        with open(path, "wb") as f:
            f.write(png_bytes)
        return path

    def test_no_vision_model_raises_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_png(tmp)
            with patch("service.llm.vision_ocr.resolve_vision_model", return_value=None):
                with self.assertRaises(ValueError) as ctx:
                    rag_service._parse_image(path, db=MagicMock(), user_id=1)
        self.assertIn("视觉", str(ctx.exception))

    def test_missing_db_or_user_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_png(tmp)
            with self.assertRaises(ValueError):
                rag_service._parse_image(path, db=None, user_id=None)

    def test_successful_ocr_returns_recognized_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tmp_png(tmp)
            with patch("service.llm.vision_ocr.resolve_vision_model",
                       return_value=("glm-4v", "fake-key", None)), \
                 patch("service.llm.vision_ocr.ocr_image", return_value="识别出的文字"):
                result = rag_service._parse_image(path, db=MagicMock(), user_id=1)
        self.assertEqual(result, "识别出的文字")


class ParsePdfWithOcrFallbackTest(unittest.TestCase):
    def _mock_reader(self, page_texts):
        pages = []
        for text in page_texts:
            page = MagicMock()
            page.extract_text.return_value = text
            pages.append(page)
        return pages

    def test_scanned_page_ocr_succeeds_when_vision_model_available(self):
        pages = self._mock_reader(["", "有文字的第二页"])
        fake_pixmap = MagicMock()
        fake_pixmap.tobytes.return_value = b"fake-png-bytes"
        fake_doc = MagicMock()
        fake_doc.__getitem__.return_value.get_pixmap.return_value = fake_pixmap

        with patch("pypdf.PdfReader") as mock_reader_cls, \
             patch("service.llm.vision_ocr.resolve_vision_model",
                   return_value=("glm-4v", "fake-key", None)), \
             patch("service.llm.vision_ocr.ocr_image", return_value="扫描页识别文字"), \
             patch("pymupdf.open", return_value=fake_doc):
            mock_reader_cls.return_value.pages = pages
            result = rag_service._parse_pdf("fake.pdf", db=MagicMock(), user_id=1)

        self.assertIn("[第1页·OCR识别]\n扫描页识别文字", result)
        self.assertIn("[第2页]\n有文字的第二页", result)

    def test_ocr_failure_on_one_page_does_not_break_others(self):
        pages = self._mock_reader(["", "第二页文字"])
        fake_doc = MagicMock()
        fake_doc.__getitem__.return_value.get_pixmap.side_effect = Exception("渲染失败")

        with patch("pypdf.PdfReader") as mock_reader_cls, \
             patch("service.llm.vision_ocr.resolve_vision_model",
                   return_value=("glm-4v", "fake-key", None)), \
             patch("pymupdf.open", return_value=fake_doc):
            mock_reader_cls.return_value.pages = pages
            result = rag_service._parse_pdf("fake.pdf", db=MagicMock(), user_id=1)

        self.assertNotIn("OCR识别", result)
        self.assertIn("[第2页]\n第二页文字", result)

    def test_no_vision_model_falls_back_to_skip(self):
        pages = self._mock_reader(["", "第二页文字"])
        with patch("pypdf.PdfReader") as mock_reader_cls, \
             patch("service.llm.vision_ocr.resolve_vision_model", return_value=None):
            mock_reader_cls.return_value.pages = pages
            result = rag_service._parse_pdf("fake.pdf", db=MagicMock(), user_id=1)

        self.assertNotIn("[第1页]", result)
        self.assertIn("[第2页]\n第二页文字", result)

    def test_no_db_or_user_id_keeps_old_skip_behavior(self):
        """向后兼容：不传 db/user_id 时（比如老测试/其它调用方）行为和之前完全一样。"""
        pages = self._mock_reader(["", "第二页文字"])
        with patch("pypdf.PdfReader") as mock_reader_cls:
            mock_reader_cls.return_value.pages = pages
            result = rag_service._parse_pdf("fake.pdf")

        self.assertNotIn("[第1页]", result)
        self.assertIn("[第2页]\n第二页文字", result)

    def test_respects_max_ocr_pages_cap(self):
        page_texts = [""] * 3
        pages = self._mock_reader(page_texts)
        fake_pixmap = MagicMock()
        fake_pixmap.tobytes.return_value = b"fake-png-bytes"
        fake_doc = MagicMock()
        fake_doc.__getitem__.return_value.get_pixmap.return_value = fake_pixmap

        with patch("pypdf.PdfReader") as mock_reader_cls, \
             patch("service.llm.vision_ocr.resolve_vision_model",
                   return_value=("glm-4v", "fake-key", None)), \
             patch("service.llm.vision_ocr.ocr_image", return_value="OCR文字") as mock_ocr, \
             patch("pymupdf.open", return_value=fake_doc), \
             patch.object(rag_service, "MAX_OCR_PAGES_PER_DOCUMENT", 2):
            mock_reader_cls.return_value.pages = pages
            rag_service._parse_pdf("fake.pdf", db=MagicMock(), user_id=1)

        self.assertEqual(mock_ocr.call_count, 2)  # 第3页超过上限，不再调用 OCR


if __name__ == "__main__":
    unittest.main()
