# RAG Evaluation

本项目提供一套轻量 RAG 评估接口，用于检查知识库检索和答案是否可靠。

## 指标

| 指标 | 含义 | 需要标注 |
| --- | --- | --- |
| 命中率 hit_rate | 每个问题的检索结果是否至少命中一个标准答案来源 | `expected_chunk_ids`、`expected_knowledge_ids` 或 `expected_texts` |
| 召回率 recall | 每个问题标注的相关来源中，有多少被 top_k 检索出来 | 同上 |
| Precision@K | top_k 检索结果里，有多少比例是相关片段 | 同上 |
| MRR | 第一个相关片段排得有多靠前，越接近 1 越好 | 同上 |
| 忠诚度 faithfulness | 答案中的事实性句子是否能被检索上下文支持 | `answer` |

默认忠诚度是无外部依赖的词面重合启发式评估，适合做回归检查和面试演示。如果传入 `faithfulness_judge_model`，系统会调用对应模型做 LLM-as-judge，让模型逐条判断答案 claim 是否被上下文支持。

## 接口

```http
POST /evaluation/{agent_id}/rag
Authorization: Bearer <token>
Content-Type: application/json
```

请求示例：

```json
{
  "top_k": 5,
  "faithfulness_judge_model": "gpt-4o-mini",
  "cases": [
    {
      "question": "RAG 知识库入库流程是什么？",
      "expected_knowledge_ids": [1],
      "expected_texts": ["上传文档后解析、切片、生成 embedding，并写入向量库"],
      "answer": "上传文档后，系统会解析文本、切片、生成 embedding，然后写入向量库。"
    }
  ]
}
```

返回中的 `metrics` 汇总整体结果，`cases` 展示每个问题的命中、召回、检索片段和忠诚度明细。

如果不想消耗模型调用成本，可以省略 `faithfulness_judge_model`，系统会使用本地启发式忠诚度评估。

## 使用建议

1. 先从 10 到 20 条高频问题开始做标注集。
2. 每条问题至少标注一个 `expected_knowledge_ids` 或 `expected_texts`。
3. 如果需要更精确的召回率，优先标注 `expected_chunk_ids`。
4. 每次修改切片、Embedding、Rerank 或 Prompt 后跑一遍同一份评估集，对比 `hit_rate`、`recall`、`precision_at_k`、`mrr`、`faithfulness`。
5. 面试或演示时，可以展示同一批问题在开启/关闭 Rerank 前后的 `MRR` 变化，这比只说“效果更好”更有说服力。
