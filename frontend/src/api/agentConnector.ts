import request from '../utils/request'

export interface ApiConnectorParam {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean'
  description?: string
  required: boolean
}

export interface ApiConnector {
  id: number
  agent_id: number
  name: string
  description: string
  url: string
  method: 'GET' | 'POST'
  has_headers: boolean
  param_schema: { type: 'object'; properties: Record<string, any>; required?: string[] }
  static_query: Record<string, any>
  is_enabled: boolean
  created_at: string | null
}

export interface CreateApiConnectorPayload {
  name: string
  description: string
  url: string
  method: 'GET' | 'POST'
  headers?: Record<string, string>
  param_schema?: { type: 'object'; properties: Record<string, any>; required?: string[] }
  static_query?: Record<string, any>
}

/** 列出这个助手配置的企业接口工具 */
export async function listApiConnectors(agentId: number): Promise<ApiConnector[]> {
  const { data } = await request.get(`/agent/${agentId}/api-connectors`)
  return data as ApiConnector[]
}

/** 新建一个企业接口工具 */
export async function createApiConnector(agentId: number, payload: CreateApiConnectorPayload): Promise<ApiConnector> {
  const { data } = await request.post(`/agent/${agentId}/api-connectors`, payload)
  return data as ApiConnector
}

/** 启用/停用一个企业接口工具 */
export async function setApiConnectorEnabled(connectorId: number, isEnabled: boolean): Promise<ApiConnector> {
  const { data } = await request.patch(`/agent/api-connectors/${connectorId}`, { is_enabled: isEnabled })
  return data as ApiConnector
}

/** 删除一个企业接口工具 */
export async function deleteApiConnector(connectorId: number): Promise<{ message: string }> {
  const { data } = await request.delete(`/agent/api-connectors/${connectorId}`)
  return data
}
