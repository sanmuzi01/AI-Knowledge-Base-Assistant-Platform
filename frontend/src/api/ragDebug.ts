import request from '../utils/request'
import type { Citation, RagSavings } from './chat'

export type { RagSavings }

export interface RagDebugHit {
  chunk_id: number | null
  knowledge_id: number | null
  chunk_index: number | null
  content: string
  score: number | null
  rerank_score: number | null
  distance: number | null
  citation_index: number | null
  source: {
    space_id: number | null
    space_name: string
    file_name: string
    file_type: string
    category: string | null
    version: string | null
    source_url: string | null
  }
}

export interface RagFaithfulness {
  score: number | null
  supported_claims: number
  claim_count: number
  unsupported_claims: string[]
  details: Array<{ claim: string; support_score?: number; supported: boolean }>
  method: string
}

export interface RagDebugTrace {
  query: string
  mode: 'spaces' | 'agent' | string
  space_ids: number[]
  agent_id: number | null
  top_k: number
  rerank: boolean
  refused: boolean
  hit_count: number
  hits: RagDebugHit[]
  context: string
  citations: Citation[]
  stats?: RagSavings | null
  answer: string | null
  answer_error?: string
  answer_model?: string
  faithfulness: RagFaithfulness | null
}

export interface RagDebugRunPayload {
  query: string
  space_ids?: number[]
  agent_id?: number | null
  top_k?: number
  rerank?: boolean | null
  refuse_when_empty?: boolean
  with_answer?: boolean
  model_name?: string | null
}

export interface RagDebugSample {
  id: number
  query: string
  space_id: number | null
  space_ids: number[]
  agent_id: number | null
  top_k: number | null
  rerank_enabled: number
  verdict: 'useful' | 'useless' | null
  in_eval_set: boolean
  hit_count: number
  has_answer: boolean
  result: RagDebugTrace | null
  created_at: string | null
  updated_at: string | null
}

export async function runRagDebug(payload: RagDebugRunPayload): Promise<RagDebugTrace> {
  const { data } = await request.post<RagDebugTrace>('/rag-debug/run', payload)
  return data
}

export async function saveRagDebugSample(payload: {
  query: string
  result: RagDebugTrace
  space_ids?: number[]
  agent_id?: number | null
  top_k?: number
  rerank?: boolean
  verdict?: 'useful' | 'useless' | null
  in_eval_set?: boolean
}): Promise<RagDebugSample> {
  const { data } = await request.post<RagDebugSample>('/rag-debug/samples', payload)
  return data
}

export async function listRagDebugSamples(params: {
  space_id?: number
  agent_id?: number
  eval_only?: boolean
} = {}): Promise<{ items: RagDebugSample[]; total: number }> {
  const { data } = await request.get('/rag-debug/samples', { params })
  return data
}

export async function patchRagDebugSample(
  id: number,
  patch: { verdict?: 'useful' | 'useless' | null; in_eval_set?: boolean },
): Promise<RagDebugSample> {
  const { data } = await request.patch<RagDebugSample>(`/rag-debug/samples/${id}`, patch)
  return data
}

export async function deleteRagDebugSample(id: number): Promise<{ message: string; id: number }> {
  const { data } = await request.delete(`/rag-debug/samples/${id}`)
  return data
}

export async function exportRagEvalCases(params: {
  space_id?: number
  agent_id?: number
} = {}): Promise<{ cases: any[]; total: number }> {
  const { data } = await request.get('/rag-debug/samples/export', { params })
  return data
}
