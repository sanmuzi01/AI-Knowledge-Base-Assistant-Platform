import request from '../utils/request'

export interface KnowledgeDoc {
  id: number
  agent_id?: number
  agent_name?: string | null
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

export interface KnowledgeRecommendation {
  key: string
  level: 'danger' | 'warn' | 'info'
  title: string
  description: string
  action_text: string
  action_path: string
}

export interface KnowledgeDiagnostics {
  agent: {
    id: number
    name: string
    rag_enabled: number
  }
  score: number
  embedding: {
    ready: boolean
    models: string[]
  }
  documents: {
    status: Record<string, number>
    searchable_count: number
    working_count: number
    failed_count: number
  }
  tasks: {
    status: Record<string, number>
    active_count: number
    failed_count: number
  }
  crawler: {
    app_env: string
    browser_fallback: boolean
    allow_private_network: boolean
    allow_private_dns: boolean
    timeout_seconds: number
    max_bytes: number
    min_text_length: number
    user_agent: string
  }
  recommendations: KnowledgeRecommendation[]
}

export interface CrawlCheckResult {
  count: number
  ok_count: number
  failed_count: number
  items: Array<{
    url: string
    normalized_url: string
    ok: boolean
    error: string
  }>
}

/** 上传文档（multipart/form-data） */
export async function uploadDocument(agentId: number, file: File, chunkSize?: number | null): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  if (chunkSize != null) formData.append('chunk_size', String(chunkSize))
  const { data } = await request.post(`/knowledge/${agentId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 批量上传文档（multipart/form-data） */
export async function uploadDocuments(agentId: number, files: File[], chunkSize?: number | null): Promise<{
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
  if (chunkSize != null) formData.append('chunk_size', String(chunkSize))
  const { data } = await request.post(`/knowledge/${agentId}/upload-batch`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 抓取网页并作为 Markdown 文档入库 */
export async function crawlDocuments(agentId: number, urls: string[]): Promise<{
  message: string
  count: number
  failed_count?: number
  items: Array<{
    file_name: string
    knowledge_id: number
    task_id: number
    status: string
    url?: string
    title?: string
  }>
  failed_items?: Array<{
    url: string
    error: string
  }>
}> {
  const { data } = await request.post(`/knowledge/${agentId}/crawl`, { urls })
  return data
}

/** 检测网页地址是否允许抓取，不创建入库任务 */
export async function checkCrawlUrls(urls: string[]): Promise<CrawlCheckResult> {
  const { data } = await request.post('/knowledge/crawl/check', { urls })
  return data
}

/** 知识库健康诊断 */
export async function getDiagnostics(agentId: number): Promise<KnowledgeDiagnostics> {
  const { data } = await request.get(`/knowledge/${agentId}/diagnostics`)
  return data
}

/** 文档列表 */
export async function listDocuments(agentId: number): Promise<KnowledgeDoc[]> {
  const { data } = await request.get(`/knowledge/${agentId}/list`)
  return data as KnowledgeDoc[]
}

/** 我的全部资料（跨助手） */
export async function listMyDocuments(): Promise<KnowledgeDoc[]> {
  const { data } = await request.get('/knowledge/my/list')
  return data as KnowledgeDoc[]
}

/** 把已有资料导入当前助手 */
export async function importDocumentToAgent(agentId: number, knowledgeId: number): Promise<any> {
  const { data } = await request.post(`/knowledge/${agentId}/import/${knowledgeId}`)
  return data
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

export async function reindexDocument(
  agentId: number,
  knowledgeId: number,
  chunkSize?: number | null,
): Promise<any> {
  const body = chunkSize === undefined ? undefined : { chunk_size: chunkSize }
  const { data } = await request.post(`/knowledge/${agentId}/${knowledgeId}/reindex`, body)
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
