import request from '../utils/request'

export interface AgentPayload {
  name: string
  model_name?: string
  role?: string | null
  task?: string | null
  constraints?: string | null
  output?: string | null
  rag_enabled?: number
  memory_enabled?: number
  temperature?: number
  skill_ids?: number[]
}

export interface AgentTemplate {
  id: string
  name: string
  description: string
  role: string
  task: string
  constraints: string
  output: string
  model_name: string
  rag_enabled: number
  memory_enabled: number
  temperature: number
  skill_names: string[]
  source?: 'builtin' | 'custom'
  editable?: boolean
  created_at?: string
  updated_at?: string
}

export interface AgentInfo extends AgentPayload {
  id: number
  user_id: number
  create_time?: string
  skills?: any[]
  prompt?: {
    role?: string
    task?: string
    constraints?: string
    output?: string
  } | null
  is_selected?: boolean
}

export interface AgentDebugInfo {
  agent: {
    id: number
    name: string
    model_name: string
    temperature: number
    rag_enabled: number
    memory_enabled: number
  }
  readiness: {
    model_configured: boolean
    embedding_configured: boolean
    rag_ready: boolean
    skill_count: number
    tool_count: number
    knowledge_done_count: number
    knowledge_total_count: number
  }
  prompt: {
    raw: Record<string, any>
    base_prompt: string
    skill_prompt: string
    final_prompt: string
  }
  skills: any[]
  tool_names: string[]
  tool_defaults_map: Record<string, Record<string, any>>
  permissions?: {
    network: boolean
    file_read: string[]
    exec: boolean
  }
  resources?: Array<{
    name: string
    path: string
    exists: boolean
    size: number
    allowed: boolean
    skill_name?: string
  }>
  knowledge: Array<{
    id: number
    file_name: string
    status: string
    chunk_count: number
    error_msg?: string | null
  }>
}

export interface AgentDryRunInfo {
  agent: AgentDebugInfo['agent']
  readiness: AgentDebugInfo['readiness']
  conversation: { id: number; title: string } | null
  input: {
    message: string
    conversation_id?: number | null
  }
  rag: {
    enabled: boolean
    ok: boolean
    error: string
    hit_count: number
    results: Array<{
      content: string
      score?: number
      distance?: number
      file_name?: string
      knowledge_id?: number
      chunk_index?: number
    }>
    context_preview: string
  }
  skills: any[]
  tool_names: string[]
  tool_defaults_map: Record<string, Record<string, any>>
  permissions?: AgentDebugInfo['permissions']
  resources?: AgentDebugInfo['resources']
  prompt: {
    base_prompt: string
    skill_prompt: string
    final_prompt: string
  }
  messages: Array<{ role: string; content: string }>
  stats: {
    history_message_count: number
    final_prompt_chars: number
    message_count: number
    tool_count: number
  }
}

export async function listAgents(): Promise<AgentInfo[]> {
  const { data } = await request.get('/agent/list')
  return data as AgentInfo[]
}

export async function listAgentTemplates(): Promise<AgentTemplate[]> {
  const { data } = await request.get('/agent/templates')
  return data as AgentTemplate[]
}

export async function createAgentTemplate(payload: Omit<AgentTemplate, 'id' | 'source' | 'editable' | 'created_at' | 'updated_at'>): Promise<AgentTemplate> {
  const { data } = await request.post('/agent/templates', payload)
  return data as AgentTemplate
}

export async function deleteAgentTemplate(templateId: string) {
  const { data } = await request.delete(`/agent/templates/${templateId}`)
  return data
}

export async function getSelectedAgent(): Promise<AgentInfo | null> {
  try {
    const { data } = await request.get('/agent/selected/me')
    return data as AgentInfo | null
  } catch {
    return null
  }
}

export async function getAgent(agentId: number): Promise<AgentInfo> {
  const { data } = await request.get(`/agent/${agentId}`)
  return data as AgentInfo
}

export async function getAgentDebug(agentId: number): Promise<AgentDebugInfo> {
  const { data } = await request.get(`/agent/${agentId}/debug`)
  return data as AgentDebugInfo
}

export async function dryRunAgent(agentId: number, payload: {
  message: string
  conversation_id?: number | null
}): Promise<AgentDryRunInfo> {
  const { data } = await request.post(`/agent/${agentId}/dry-run`, payload)
  return data as AgentDryRunInfo
}

export async function createAgent(payload: AgentPayload): Promise<{ agent_id: number }> {
  const { data } = await request.post('/agent', payload)
  return data as { agent_id: number }
}

export async function cloneAgent(agentId: number, payload: { name?: string | null } = {}): Promise<{ agent_id: number }> {
  const { data } = await request.post(`/agent/${agentId}/clone`, payload)
  return data as { agent_id: number }
}

export async function updateAgent(agentId: number, payload: Partial<AgentPayload>) {
  const { data } = await request.put(`/agent/${agentId}`, payload)
  return data
}

export async function deleteAgent(agentId: number) {
  const { data } = await request.delete(`/agent/${agentId}`)
  return data
}

export async function selectAgent(agentId: number) {
  const { data } = await request.post(`/agent/${agentId}/select`)
  return data
}
export interface DeletePreview {
  agent_id: number
  agent_name: string
  conversation_count: number
  message_count: number
  skill_binding_count: number
  knowledge_count: number
  run_count: number
  task_count: number
  total_impacted: number
}

/** 删除前预检影响范围 */
export async function deletePreview(agentId: number): Promise<DeletePreview> {
  const { data } = await request.get(`/agent/${agentId}/delete_preview`)
  return data as DeletePreview
}
