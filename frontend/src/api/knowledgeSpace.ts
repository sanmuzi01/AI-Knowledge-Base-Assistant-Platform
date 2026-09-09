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

// ---------------- 空间内文档 ----------------

export interface SpaceDoc {
  id: number
  file_name: string
  file_type: string
  file_size: number
  chunk_count: number
  status: string
  status_label: string
  is_enabled: number
  error_msg: string | null
  category: string | null
  tags: string[]
  version: string | null
  source_type: string
  source_url: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SpaceDocListResponse {
  items: SpaceDoc[]
  total: number
  facets: {
    categories: string[]
    tags: string[]
    statuses: { key: string; label: string }[]
  }
}

export interface DocFilter {
  category?: string
  tag?: string
  doc_status?: string
  enabled?: boolean
}

export async function listSpaceDocs(spaceId: number, filter: DocFilter = {}): Promise<SpaceDocListResponse> {
  const { data } = await request.get<SpaceDocListResponse>(`/knowledge-spaces/${spaceId}/documents`, {
    params: filter,
  })
  return data
}

export async function uploadSpaceDoc(
  spaceId: number,
  file: File,
  meta: { category?: string; version?: string } = {},
): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await request.post(`/knowledge-spaces/${spaceId}/documents`, form, {
    params: meta,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function crawlSpaceDocs(spaceId: number, urls: string[]): Promise<any> {
  const { data } = await request.post(`/knowledge-spaces/${spaceId}/documents/crawl`, { urls })
  return data
}

export async function updateSpaceDoc(
  spaceId: number,
  knowledgeId: number,
  patch: { category?: string; tags?: string[]; version?: string; is_enabled?: boolean },
): Promise<any> {
  const { data } = await request.patch(`/knowledge-spaces/${spaceId}/documents/${knowledgeId}`, patch)
  return data
}

export async function reindexSpaceDoc(spaceId: number, knowledgeId: number): Promise<any> {
  const { data } = await request.post(`/knowledge-spaces/${spaceId}/documents/${knowledgeId}/reindex`)
  return data
}

export async function deleteSpaceDoc(spaceId: number, knowledgeId: number): Promise<any> {
  const { data } = await request.delete(`/knowledge-spaces/${spaceId}/documents/${knowledgeId}`)
  return data
}
