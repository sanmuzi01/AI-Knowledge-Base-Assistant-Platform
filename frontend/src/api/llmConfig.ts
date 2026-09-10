import request from '../utils/request'

export interface LlmConfig {
  id: number
  model_name: string
  api_key: string
  api_url?: string | null
  provider?: string
  kind?: 'chat' | 'embedding' | string
  is_active: number
}

export interface LlmConfigPayload {
  model_name: string
  api_key: string
}

export interface SupportedModel {
  model_name: string
  provider: string
  kind: 'chat' | 'embedding'
}

export interface LlmConfigTestResult {
  ok: boolean
  model_name: string
  kind?: 'chat' | 'embedding' | string
  message: string
  elapsed_ms?: number
  dimension?: number
  preview?: string
  error?: string
}

export async function listConfigs(): Promise<LlmConfig[]> {
  const { data } = await request.get('/llm_config/list')
  return data as LlmConfig[]
}

export async function saveConfig(payload: LlmConfigPayload) {
  const { data } = await request.post('/llm_config', payload)
  return data
}

export async function deleteConfig(modelName: string) {
  const { data } = await request.delete(`/llm_config/${encodeURIComponent(modelName)}`)
  return data
}

export async function testConfig(modelName: string): Promise<LlmConfigTestResult> {
  const { data } = await request.post(`/llm_config/${encodeURIComponent(modelName)}/test`)
  return data as LlmConfigTestResult
}

export interface QuickConnectResult {
  provider: string
  saved: string[]
  skipped: Array<{ capability: string; reason: string }>
  results: Record<string, LlmConfigTestResult>
}

/** 一次连接，多项能力：选平台 + 粘一次 Key，后端原子保存聊天+资料两条配置并逐条测试。 */
export async function quickConnect(payload: {
  provider: string
  api_key: string
  capabilities?: Array<'chat' | 'embedding'>
}): Promise<QuickConnectResult> {
  const { data } = await request.post('/llm_config/quick_connect', payload)
  return data as QuickConnectResult
}

export async function listSupportedModelCatalog(): Promise<{
  chat: SupportedModel[]
  embedding: SupportedModel[]
}> {
  const { data } = await request.get('/llm_config/supported_models')
  return {
    chat: data.chat || [],
    embedding: data.embedding || [],
  }
}
