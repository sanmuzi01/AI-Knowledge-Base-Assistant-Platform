import request from '../utils/request'

export interface KnowledgeSpace {
  id: number
  name: string
  description: string
  purpose: string | null
  purpose_label: string
  tags: string[]
  is_enabled: boolean
  status: 'active' | 'archived'
  doc_count: number
  chunk_count: number
  bound_agent_count?: number
  health_score: number | null
  last_indexed_at: string | null
  created_at: string | null
  updated_at: string | null
  scope: string
  my_role: string
}

export interface SpaceListResponse {
  items: KnowledgeSpace[]
  purposes: { key: string; label: string }[]
}

export interface SpaceCreatePayload {
  name: string
  description?: string
  purpose?: string | null
  tags?: string[]
}

export type SpaceUpdatePayload = Partial<SpaceCreatePayload> & {
  is_enabled?: boolean
  status?: 'active' | 'archived'
}

export async function listSpaces(): Promise<SpaceListResponse> {
  const { data } = await request.get<SpaceListResponse>('/knowledge-spaces')
  return data
}

export async function getSpace(id: number): Promise<KnowledgeSpace> {
  const { data } = await request.get<KnowledgeSpace>(`/knowledge-spaces/${id}`)
  return data
}

export async function createSpace(payload: SpaceCreatePayload): Promise<KnowledgeSpace> {
  const { data } = await request.post<KnowledgeSpace>('/knowledge-spaces', payload)
  return data
}

export async function updateSpace(id: number, patch: SpaceUpdatePayload): Promise<KnowledgeSpace> {
  const { data } = await request.patch<KnowledgeSpace>(`/knowledge-spaces/${id}`, patch)
  return data
}

export async function deleteSpace(id: number): Promise<{ message: string; id: number }> {
  const { data } = await request.delete(`/knowledge-spaces/${id}`)
  return data
}
