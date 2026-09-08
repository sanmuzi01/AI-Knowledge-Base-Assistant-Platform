import request from '../utils/request'

export interface RagEvalCase {
  question: string
  expected_chunk_ids?: number[]
  expected_knowledge_ids?: number[]
  expected_texts?: string[]
  answer?: string | null
  knowledge_id?: number | null
}

export interface RagEvalRequest {
  cases: RagEvalCase[]
  top_k?: number
  knowledge_id?: number | null
  text_match_threshold?: number
  faithfulness_threshold?: number
  faithfulness_judge_model?: string | null
}

export interface RagEvalReport {
  case_count: number
  evaluated_retrieval_count: number
  evaluated_faithfulness_count: number
  metrics: {
    hit_rate: number | null
    recall: number | null
    precision_at_k: number | null
    mrr: number | null
    faithfulness: number | null
  }
  settings: Record<string, any>
  cases: Array<{
    question: string
    hit: boolean | null
    recall: number | null
    matched_units: number
    expected_units: number
    retrieved_count: number
    ranking: {
      precision_at_k: number | null
      mrr: number | null
      first_relevant_rank: number | null
      relevant_retrieved: number
    }
    retrieved: Array<{
      rank: number
      chunk_id?: number
      knowledge_id?: number
      chunk_index?: number
      score?: number
      file_name?: string
      content_preview: string
    }>
    relevance: Array<{
      rank: number
      relevant: boolean
      reasons: string[]
      matched_texts: Array<{ expected_text: string; score: number }>
    }>
    faithfulness?: {
      score: number | null
      supported_claims: number
      claim_count: number
      unsupported_claims: string[]
      method: string
      details: any[]
    } | null
    faithfulness_judge_error?: string
  }>
}

export async function evaluateRag(agentId: number, payload: RagEvalRequest): Promise<RagEvalReport> {
  const { data } = await request.post(`/evaluation/${agentId}/rag`, payload)
  return data as RagEvalReport
}
