"""split_text 按段落切分的回归测试。

之前是纯定长滑窗，不管内容结构，经常把一句话/一个编号项从中间切断。
现在优先在空行处断开、尽量把完整段落打包进一个 chunk，只有单个自然段本身
就超过 chunk_size 才退回定长滑窗切——这组测试锁定这个行为。
"""
import unittest

from service.rag.rag_service import split_text


class SplitTextParagraphTest(unittest.TestCase):
    def test_short_paragraphs_pack_into_one_chunk(self):
        text = "第一段内容比较短。\n\n第二段内容也比较短。\n\n第三段内容同样很短。"
        chunks = split_text(text, chunk_size=200, overlap=0)
        self.assertEqual(len(chunks), 1)
        self.assertIn("第一段内容比较短", chunks[0])
        self.assertIn("第三段内容同样很短", chunks[0])

    def test_paragraph_never_split_mid_sentence_when_it_fits(self):
        # 每段本身都在 chunk_size 以内，纯定长滑窗会在任意字符位置切断；
        # 按段落切分则保证每一段整体出现在某一个 chunk 里，不会被腰斩。
        para_a = "编号A-100：这是一条完整的规格说明，不应该被从中间切断。" * 2
        para_b = "编号B-200：这是另一条完整的规格说明，同样不应该被切断。" * 2
        text = f"{para_a}\n\n{para_b}"
        chunks = split_text(text, chunk_size=len(para_a) + 10, overlap=0)

        self.assertTrue(any(para_a in c for c in chunks), "para_a 应该完整出现在某个 chunk 里")
        self.assertTrue(any(para_b in c for c in chunks), "para_b 应该完整出现在某个 chunk 里")

    def test_oversized_single_paragraph_falls_back_to_fixed_window(self):
        huge_para = "超长无换行内容" * 200  # 单个自然段本身就超过 chunk_size
        chunks = split_text(huge_para, chunk_size=100, overlap=10)
        self.assertGreater(len(chunks), 1, "超长单段必须能被切开，不能整块原样返回")
        self.assertTrue(all(len(c) <= 130 for c in chunks))  # 允许 overlap 带来的少量超出

    def test_overlap_carries_context_between_chunks(self):
        para_a = "A" * 90
        para_b = "B" * 90
        text = f"{para_a}\n\n{para_b}"
        chunks = split_text(text, chunk_size=100, overlap=20)
        self.assertEqual(len(chunks), 2)
        # 第二块开头应该带上第一块结尾的一小段，缓解切分点信息丢失
        self.assertTrue(chunks[1].startswith("A" * 20) or "A" * 20 in chunks[1][:30])

    def test_page_and_table_markers_stay_as_their_own_blocks(self):
        text = "[第1页]\n开头内容。\n\n【表格】\n表头1 | 表头2\n数据1 | 数据2\n\n结尾内容。"
        chunks = split_text(text, chunk_size=500, overlap=0)
        self.assertEqual(len(chunks), 1)
        self.assertIn("[第1页]", chunks[0])
        self.assertIn("【表格】", chunks[0])

    def test_empty_and_blank_input(self):
        self.assertEqual(split_text(""), [])
        self.assertEqual(split_text("   \n\n   "), [])


if __name__ == "__main__":
    unittest.main()
