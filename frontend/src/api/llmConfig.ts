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

export async function listSupportedModels(): Promise<string[]> {
  const { data } = await request.get('/llm_config/supported_models')
  return data.models as string[]
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
