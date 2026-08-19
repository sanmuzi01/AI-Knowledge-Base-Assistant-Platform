import request from '../utils/request'

export interface KnowledgeDoc {
  id: number
  file_name: string
  file_type: string
  file_size: number
  chunk_count: number
  status: string        // pending / processing / done / failed
  is_enabled: number    // 0 / 1，是否参与RAG检索
  error_msg?: string | null
  created_at: string | null
}

export interface KnowledgeDocDetail extends KnowledgeDoc {}

export interface SearchResult {
  chunk_id?: number
  content: string
  score?: number
  distance?: number
  knowledge_id?: number
  chunk_index?: number
  file_name?: string
  file_type?: string
  metadata?: any
}

export interface KnowledgeChunk {
  id: number
  chunk_index: number
  content: string
  token_count: number
  vector_id: string
  created_at: string | null
}

/** 上传文档（multipart/form-data） */
export async function uploadDocument(agentId: number, file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await request.post(`/knowledge/${agentId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 批量上传文档（multipart/form-data） */
export async function uploadDocuments(agentId: number, files: File[]): Promise<{
  message: string
  count: number
  items: Array<{
    file_name: string
    knowledge_id: number
    task_id: number
    status: string
  }>
}> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const { data } = await request.post(`/knowledge/${agentId}/upload-batch`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 文档列表 */
export async function listDocuments(agentId: number): Promise<KnowledgeDoc[]> {
  const { data } = await request.get(`/knowledge/${agentId}/list`)
  return data as KnowledgeDoc[]
}

export async function getDocument(agentId: number, knowledgeId: number): Promise<KnowledgeDocDetail> {
  const { data } = await request.get(`/knowledge/${agentId}/${knowledgeId}`)
  return data as KnowledgeDocDetail
}

/** 检索测试 */
export async function searchKnowledge(agentId: number, payload: {
  query: string
  top_k?: number
  knowledge_id?: number | null
}): Promise<SearchResult[]> {
  const { data } = await request.post(`/knowledge/${agentId}/search`, payload)
  return data.results as SearchResult[]
}

export async function listChunks(agentId: number, knowledgeId: number): Promise<KnowledgeChunk[]> {
  const { data } = await request.get(`/knowledge/${agentId}/${knowledgeId}/chunks`)
  return data.chunks as KnowledgeChunk[]
}

export async function reindexDocument(agentId: number, knowledgeId: number): Promise<any> {
  const { data } = await request.post(`/knowledge/${agentId}/${knowledgeId}/reindex`)
  return data
}

export async function updateDocumentEnabled(agentId: number, knowledgeId: number, isEnabled: number): Promise<any> {
  const { data } = await request.patch(`/knowledge/${agentId}/${knowledgeId}/enabled`, {
    is_enabled: isEnabled,
  })
  return data
}

/** 删除文档 */
export async function deleteDocument(agentId: number, knowledgeId: number): Promise<any> {
  const { data } = await request.delete(`/knowledge/${agentId}/${knowledgeId}`)
  return data
}
