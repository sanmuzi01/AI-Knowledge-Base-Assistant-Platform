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

export interface SpaceRagEvalRequest {
  cases: RagEvalCase[]
  top_k?: number
  rerank?: boolean | null
  text_match_threshold?: number
  faithfulness_threshold?: number
}

export async function evaluateSpaceRag(spaceId: number, payload: SpaceRagEvalRequest): Promise<RagEvalReport> {
  const { data } = await request.post(`/evaluation/space/${spaceId}/rag`, payload)
  return data as RagEvalReport
}

// ============================================================================
// 固定评估集：建一次问题集，之后随时重跑，自动跟上一轮比对回归/变好的问题
// ============================================================================

export interface EvalSet {
  id: number
  name: string
  agent_id: number | null
  space_id: number | null
  cases: RagEvalCase[]
  settings: Record<string, any>
  created_at: string | null
}

export interface EvalRunDiff {
  regressed_questions: string[]
  improved_questions: string[]
  metric_deltas: Record<string, number>
}

export interface EvalRunResult {
  run_id: number
  eval_set_id: number
  report: RagEvalReport
  diff: EvalRunDiff | null
}

export interface EvalRunSummary {
  id: number
  created_at: string | null
  metrics: RagEvalReport['metrics']
}

export interface CreateEvalSetPayload {
  name: string
  agent_id?: number | null
  space_id?: number | null
  cases: RagEvalCase[]
  top_k?: number
  rerank?: boolean | null
  text_match_threshold?: number
  faithfulness_threshold?: number
  faithfulness_judge_model?: string | null
}

/** 建一份固定评估集（绑定 Agent 或知识库空间，二选一） */
export async function createEvalSet(payload: CreateEvalSetPayload): Promise<EvalSet> {
  const { data } = await request.post('/evaluation/sets', payload)
  return data as EvalSet
}

/** 列出我的固定评估集，可按 agent_id / space_id 过滤 */
export async function listEvalSets(params: { agent_id?: number; space_id?: number } = {}): Promise<EvalSet[]> {
  const { data } = await request.get('/evaluation/sets', { params })
  return data as EvalSet[]
}

/** 跑一次评估集，自动跟上一轮比较 */
export async function runEvalSet(evalSetId: number): Promise<EvalRunResult> {
  const { data } = await request.post(`/evaluation/sets/${evalSetId}/run`)
  return data as EvalRunResult
}

/** 评估集历史运行记录 */
export async function listEvalRuns(evalSetId: number): Promise<EvalRunSummary[]> {
  const { data } = await request.get(`/evaluation/sets/${evalSetId}/runs`)
  return data as EvalRunSummary[]
}

/** 删除评估集（含历史运行记录） */
export async function deleteEvalSet(evalSetId: number): Promise<{ message: string }> {
  const { data } = await request.delete(`/evaluation/sets/${evalSetId}`)
  return data
}
