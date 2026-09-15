import request from '../utils/request'

export interface AgentRun {
  id: number
  agent_id: number
  user_message: string
  status: 'running' | 'finished' | 'failed' | 'cancelled'
  total_steps: number
  final_answer?: string
  error_msg?: string
  started_at?: string
  finished_at?: string
}

export interface AgentStep {
  step_no: number
  step_type: 'agent' | 'tool' | 'retrieve' | string
  thought?: string
  tool_name?: string
  tool_args?: string | Record<string, any>
  tool_result?: string
  tokens?: number
  created_at?: string
}

export interface RunDetail {
  run_id: number
  status: string
  user_message: string
  final_answer?: string
  total_steps: number
  started_at?: string
  finished_at?: string
  steps: AgentStep[]
}

/** Agent 的运行历史（默认 limit=20） */
export async function listRuns(
  agentId: number,
  limit = 20,
  conversationId?: number | null,
): Promise<AgentRun[]> {
  const params: Record<string, any> = { limit }
  if (conversationId != null) params.conversation_id = conversationId
  const { data } = await request.get(`/run/${agentId}/list`, { params })
  return data as AgentRun[]
}

/** 单次运行的详细步骤 */
export async function getRunSteps(runId: number, full = true): Promise<RunDetail> {
  const { data } = await request.get(`/run/${runId}/steps`, { params: { full: full ? 1 : 0 } })
  return data as RunDetail
}
