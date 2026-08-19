import request from '../utils/request'

export interface MemoryItem {
  id: number
  user_id: number
  agent_id: number
  memory_type: string
  content: string
  chat_count: number
  created_at: string | null
}

export interface MemoryPayload {
  memory_type?: string
  content: string
}

export async function listMemories(agentId: number): Promise<MemoryItem[]> {
  const { data } = await request.get(`/memory/agent/${agentId}`)
  return data as MemoryItem[]
}

export async function createMemory(agentId: number, payload: MemoryPayload): Promise<MemoryItem> {
  const { data } = await request.post(`/memory/agent/${agentId}`, payload)
  return data as MemoryItem
}

export async function updateMemory(memoryId: number, payload: Partial<MemoryPayload>): Promise<MemoryItem> {
  const { data } = await request.put(`/memory/${memoryId}`, payload)
  return data as MemoryItem
}

export async function deleteMemory(memoryId: number): Promise<any> {
  const { data } = await request.delete(`/memory/${memoryId}`)
  return data
}

export async function clearMemories(agentId: number): Promise<{ message: string; count: number }> {
  const { data } = await request.delete(`/memory/agent/${agentId}`)
  return data
}
