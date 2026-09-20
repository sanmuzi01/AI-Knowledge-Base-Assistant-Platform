import request from '../utils/request'

export interface PipelineStep {
  agent_id: number
  label?: string | null
}

export interface AgentPipeline {
  id: number
  name: string
  description: string | null
  steps: PipelineStep[]
  is_enabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface PipelineStepResult {
  step: number
  agent_id: number
  agent_name?: string
  label?: string | null
  ok: boolean
  question?: string
  answer?: string
  conversation_id?: number | null
  error?: string
}

export interface PipelineRunResult {
  pipeline_id: number
  pipeline_name: string
  completed: boolean
  steps: PipelineStepResult[]
  final_answer: string | null
}

export async function listPipelines(): Promise<AgentPipeline[]> {
  const { data } = await request.get('/pipelines')
  return data as AgentPipeline[]
}

export async function createPipeline(payload: {
  name: string
  description?: string
  steps: PipelineStep[]
}): Promise<AgentPipeline> {
  const { data } = await request.post('/pipelines', payload)
  return data as AgentPipeline
}

export async function updatePipeline(id: number, patch: {
  name?: string
  description?: string
  steps?: PipelineStep[]
  is_enabled?: boolean
}): Promise<AgentPipeline> {
  const { data } = await request.patch(`/pipelines/${id}`, patch)
  return data as AgentPipeline
}

export async function deletePipeline(id: number): Promise<{ message: string }> {
  const { data } = await request.delete(`/pipelines/${id}`)
  return data
}

export async function runPipeline(id: number, message: string): Promise<PipelineRunResult> {
  const { data } = await request.post(`/pipelines/${id}/run`, { message })
  return data as PipelineRunResult
}
