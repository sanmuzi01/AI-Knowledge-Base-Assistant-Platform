<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <div class="flex items-center gap-3">
        <button
          @click="router.push('/agents')"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50"
          title="返回 Agent 列表"
        >
          <ArrowLeft :size="16" />
        </button>
        <div>
          <h1 class="text-base font-semibold text-slate-900">知识库管理</h1>
          <p class="text-xs text-slate-500">{{ currentAgent?.name || `Agent #${agentId}` }} 的文档入库与检索测试</p>
        </div>
      </div>
      <button @click="loadDocs" class="text-xs text-slate-500 hover:text-slate-900">刷新</button>
    </header>

    <main class="flex-1 overflow-hidden">
      <div class="grid h-full grid-cols-1 lg:grid-cols-[minmax(420px,1fr)_minmax(420px,1fr)]">
        <section class="flex min-h-0 flex-col border-r border-slate-200 bg-white">
          <div class="border-b border-slate-200 p-5">
            <h2 class="mb-3 text-sm font-semibold text-slate-800">上传文档</h2>
            <div
              @dragover.prevent="dragOver = true"
              @dragleave.prevent="dragOver = false"
              @drop.prevent="handleDrop"
              @click="canUseRag && fileInput?.click()"
              :class="[
                dragOver && canUseRag ? 'border-blue-500 bg-blue-50' : 'border-slate-300',
                canUseRag ? 'hover:border-slate-400' : 'cursor-not-allowed bg-slate-50 opacity-70',
              ]"
              class="cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors"
            >
              <input ref="fileInput" type="file" class="hidden" accept=".txt,.md,.pdf,.docx" multiple :disabled="!canUseRag" @change="handleFileSelect" />
              <UploadCloud :size="30" class="mx-auto mb-3 text-slate-400" />
              <p class="text-sm font-medium text-slate-700">{{ uploadTitle }}</p>
              <p class="mt-1 text-xs text-slate-500">{{ uploading ? uploadProgress : uploadHint }}</p>
            </div>
            <div v-if="!canUseRag" class="mt-3 flex items-center justify-between rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <span>{{ ragBlockedReason }}</span>
              <button @click="router.push('/llm-configs')" class="rounded border border-amber-300 bg-white px-2 py-1 hover:bg-amber-100">
                配置 Key
              </button>
            </div>
            <p v-if="uploadError" class="mt-2 text-sm text-red-600">{{ uploadError }}</p>
            <div v-if="tasks.length" class="mt-4 space-y-2">
              <article
                v-for="task in tasks"
                :key="task.id"
                class="rounded border border-slate-200 bg-slate-50 px-3 py-2"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="truncate text-xs font-medium text-slate-700">{{ task.title }}</p>
                    <p class="mt-0.5 text-xs text-slate-400">{{ task.created_at || '刚刚创建' }}</p>
                  </div>
                  <span :class="taskStatusClass(task.status)" class="shrink-0 rounded px-2 py-1 text-xs">
                    {{ taskStatusText(task.status) }}
                  </span>
                </div>
                <div class="mt-2 h-1.5 rounded bg-slate-200">
                  <div class="h-1.5 rounded bg-blue-500 transition-all" :style="{ width: `${task.progress || 0}%` }"></div>
                </div>
                <p v-if="task.error_msg" class="mt-2 line-clamp-2 text-xs text-red-600">{{ task.error_msg }}</p>
              </article>
            </div>
          </div>

          <div class="flex min-h-0 flex-1 flex-col p-5">
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-sm font-semibold text-slate-800">文档列表</h2>
              <span class="text-xs text-slate-400">{{ docs.length }} 个文档</span>
            </div>

            <div v-if="docs.length === 0" class="flex flex-1 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">
              还没有文档。上传后会自动解析、切块并写入向量库。
            </div>

            <div v-else class="min-h-0 flex-1 overflow-y-auto space-y-2 pr-1">
              <article
                v-for="doc in docs"
                :key="doc.id"
                class="rounded-lg border border-slate-200 p-3 hover:border-slate-300"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="flex min-w-0 gap-3">
                    <span class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded bg-slate-100 text-slate-600">
                      <component :is="fileIcon(doc.file_type)" :size="17" />
                    </span>
                    <div class="min-w-0">
                      <h3 class="truncate text-sm font-medium text-slate-900">{{ doc.file_name }}</h3>
                      <p class="mt-1 text-xs text-slate-500">
                        {{ doc.file_type.toUpperCase() }} · {{ formatSize(doc.file_size) }} · {{ doc.chunk_count }} 块
                      </p>
                      <p class="mt-1 text-xs text-slate-400">{{ doc.created_at || '无创建时间' }}</p>
                      <p v-if="doc.status === 'failed' && doc.error_msg" class="mt-1 line-clamp-2 text-xs text-red-600">{{ doc.error_msg }}</p>
                    </div>
                  </div>
                  <span :class="statusClass(doc.status)" class="shrink-0 rounded px-2 py-1 text-xs">
                    {{ statusText(doc.status) }}
                  </span>
                </div>
                <div class="mt-3 flex justify-end">
                  <button
                    @click="handleToggleEnabled(doc)"
                    :disabled="togglingEnabledId === doc.id"
                    :class="doc.is_enabled === 1 ? 'border-amber-100 text-amber-700 hover:bg-amber-50' : 'border-emerald-100 text-emerald-700 hover:bg-emerald-50'"
                    class="mr-2 rounded border px-3 py-1.5 text-xs disabled:text-slate-300"
                    :title="doc.is_enabled === 1 ? '禁用后不参与RAG检索' : '启用后参与RAG检索'"
                  >
                    {{ togglingEnabledId === doc.id ? '更新中...' : doc.is_enabled === 1 ? '禁用' : '启用' }}
                  </button>
                  <button
                    @click="handleReindex(doc)"
                    :disabled="!canUseRag || reindexingId === doc.id"
                    class="mr-2 rounded border border-blue-100 px-3 py-1.5 text-xs text-blue-700 hover:bg-blue-50 disabled:text-slate-300"
                    title="重新入库"
                  >
                    {{ reindexingId === doc.id ? '重建中...' : '重建' }}
                  </button>
                  <button
                    @click="openChunks(doc)"
                    class="mr-2 rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    title="查看片段"
                  >
                    片段
                  </button>
                  <button
                    @click="handleDelete(doc)"
                    class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除文档"
                  >
                    <Trash2 :size="15" />
                  </button>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section class="flex min-h-0 flex-col bg-slate-50">
          <div class="border-b border-slate-200 bg-white p-5">
            <h2 class="mb-3 text-sm font-semibold text-slate-800">检索测试</h2>
            <div class="mb-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_96px]">
              <select
                v-model="selectedKnowledgeId"
                class="h-9 rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500"
              >
                <option :value="0">全部已入库文档</option>
                <option v-for="doc in searchableDocs" :key="doc.id" :value="doc.id">
                  {{ doc.file_name }}
                </option>
              </select>
              <select
                v-model.number="topK"
                class="h-9 rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500"
              >
                <option :value="3">Top 3</option>
                <option :value="5">Top 5</option>
                <option :value="10">Top 10</option>
              </select>
            </div>
            <div class="flex gap-2">
              <input
                v-model="searchQuery"
                type="text"
                class="h-10 flex-1 rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                placeholder="输入问题或关键词，测试 RAG 命中片段"
                @keydown.enter="handleSearch"
              />
              <button
                @click="handleSearch"
                :disabled="searching || !searchQuery.trim() || !canUseRag"
                class="inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-300"
              >
                <Search :size="15" />
                {{ searching ? '检索中...' : '检索' }}
              </button>
            </div>
            <p v-if="searchError" class="mt-2 text-sm text-red-600">{{ searchError }}</p>
            <p v-else-if="searchingSlow" class="mt-2 text-xs text-amber-700">
              检索仍在处理。如果长时间没有返回，请确认后端服务正常、向量模型 Key 可用，或查看运行日志。
            </p>
            <p v-else-if="!canUseRag" class="mt-2 text-xs text-amber-700">{{ ragBlockedReason }}</p>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto p-5">
            <div v-if="searchResults.length === 0 && !searching" class="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 text-center text-sm text-slate-500">
              {{ hasSearched ? '没有命中相关片段。可以换个关键词，或确认文档状态为已完成。' : '检索结果会显示在这里。' }}
            </div>

            <div v-else class="space-y-3">
              <article
                v-for="(result, i) in searchResults"
                :key="i"
                class="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-medium text-blue-700">片段 {{ i + 1 }}</span>
                  <span v-if="typeof result.score === 'number'" class="text-xs text-slate-400">分数 {{ formatScore(result.score) }}</span>
                </div>
                <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span v-if="result.file_name">{{ result.file_name }}</span>
                  <span v-if="typeof result.chunk_index === 'number'">第 {{ result.chunk_index + 1 }} 块</span>
                  <span v-if="typeof result.distance === 'number'">距离 {{ result.distance.toFixed(4) }}</span>
                </div>
                <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ result.content }}</p>
              </article>
            </div>
          </div>
        </section>
      </div>
    </main>

    <div v-if="showChunks" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="closeChunks">
      <div class="flex max-h-[82vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-slate-900">{{ chunkDoc?.file_name || '文档片段' }}</h2>
            <p class="text-xs text-slate-500">{{ chunks.length }} 个片段</p>
          </div>
          <button @click="closeChunks" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            ×
          </button>
        </header>
        <main class="min-h-0 flex-1 overflow-y-auto p-5">
          <div v-if="chunksLoading" class="py-16 text-center text-sm text-slate-500">加载中...</div>
          <div v-else-if="chunks.length === 0" class="py-16 text-center text-sm text-slate-500">暂无片段。</div>
          <div v-else class="space-y-3">
            <article v-for="chunk in chunks" :key="chunk.id" class="rounded border border-slate-200 p-4">
              <div class="mb-2 flex items-center justify-between text-xs text-slate-400">
                <span>片段 {{ chunk.chunk_index + 1 }}</span>
                <span>{{ chunk.token_count }} tokens</span>
              </div>
              <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ chunk.content }}</p>
            </article>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, File, FileText, Search, Trash2, UploadCloud } from 'lucide-vue-next'
import * as agentApi from '../api/agent'
import type { AgentInfo } from '../api/agent'
import * as llmConfigApi from '../api/llmConfig'
import type { LlmConfig } from '../api/llmConfig'
import * as knowledgeApi from '../api/knowledge'
import type { KnowledgeChunk, KnowledgeDoc, SearchResult } from '../api/knowledge'
import * as taskApi from '../api/task'
import type { BackgroundTask } from '../api/task'
import { getErrorMessage } from '../utils/request'

const router = useRouter()
const route = useRoute()
const agentId = computed(() => Number(route.params.agentId))
const currentAgent = ref<AgentInfo | null>(null)
const configs = ref<LlmConfig[]>([])
const configError = ref('')

const docs = ref<KnowledgeDoc[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const uploading = ref(false)
const uploadProgress = ref('')
const uploadError = ref('')
const searchQuery = ref('')
const searching = ref(false)
const searchingSlow = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchError = ref('')
const hasSearched = ref(false)
const selectedKnowledgeId = ref(0)
const topK = ref(5)
const showChunks = ref(false)
const chunksLoading = ref(false)
const chunks = ref<KnowledgeChunk[]>([])
const chunkDoc = ref<KnowledgeDoc | null>(null)
const reindexingId = ref<number | null>(null)
const togglingEnabledId = ref<number | null>(null)
const tasks = ref<BackgroundTask[]>([])
let pollTimer: number | undefined
let searchSlowTimer: number | undefined
let taskPollTimer: number | undefined

const searchableDocs = computed(() => docs.value.filter((doc) => doc.status === 'done' && doc.chunk_count > 0 && doc.is_enabled !== 0))
const hasEmbeddingKey = computed(() => configs.value.some((config) => {
  const model = config.model_name.toLowerCase()
  return model.includes('embedding') || model.startsWith('baai/') || model === 'glm-4'
}))
const ragBlockedReason = computed(() => {
  if (configError.value) return configError.value
  if (!hasEmbeddingKey.value) return '当前用户还没有配置 RAG 向量模型 Key'
  return ''
})
const canUseRag = computed(() => !ragBlockedReason.value)
const uploadTitle = computed(() => {
  if (uploading.value) return '正在创建入库任务...'
  if (!canUseRag.value) return '请先配置向量模型 Key'
  return '点击或拖拽文件到这里'
})
const uploadHint = computed(() => canUseRag.value ? '支持批量选择 txt / md / pdf / docx' : '配置后才能上传、切块和检索')

const loadCurrentAgent = async () => {
  try {
    const agentList = await agentApi.listAgents()
    currentAgent.value = agentList.find((agent) => agent.id === agentId.value) || null
  } catch {
    currentAgent.value = null
  }
}

const loadConfigs = async () => {
  configError.value = ''
  try {
    configs.value = await llmConfigApi.listConfigs()
  } catch (e: any) {
    configs.value = []
    configError.value = getErrorMessage(e, '无法读取模型 Key 配置')
  }
}

const loadDocs = async () => {
  try {
    docs.value = await knowledgeApi.listDocuments(agentId.value)
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '读取知识库文档失败')
    docs.value = []
    updatePolling()
  }
}

const loadPage = async () => {
  await Promise.all([loadCurrentAgent(), loadConfigs()])
  await loadDocs()
  await loadTasks()
}

const updatePolling = () => {
  const hasWorkingDoc = docs.value.some((doc) => doc.status === 'pending' || doc.status === 'processing')
  const hasWorkingTask = tasks.value.some((task) => task.status === 'queued' || task.status === 'running')
  if (hasWorkingDoc && pollTimer === undefined) {
    pollTimer = window.setInterval(loadDocs, 3000)
  }
  if (!hasWorkingDoc && pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
  if (hasWorkingTask && taskPollTimer === undefined) {
    taskPollTimer = window.setInterval(loadTasks, 2500)
  }
  if (!hasWorkingTask && taskPollTimer !== undefined) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = undefined
  }
}

const loadTasks = async () => {
  try {
    const allTasks = await taskApi.listTasks(20)
    tasks.value = allTasks
      .filter((task) => task.agent_id === agentId.value && task.target_type === 'knowledge')
      .slice(0, 5)
  } catch {
    tasks.value = tasks.value.filter((task) => task.status === 'queued' || task.status === 'running')
  } finally {
    updatePolling()
  }
}

const uploadFiles = async (files: File[]) => {
  if (!canUseRag.value) {
    uploadError.value = ragBlockedReason.value
    return
  }
  const uploadList = files.filter(Boolean)
  if (uploadList.length === 0) return
  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = uploadList.length === 1 ? uploadList[0].name : `${uploadList.length} 个文件`
  try {
    const result = uploadList.length === 1
      ? {
          items: [{
            file_name: uploadList[0].name,
            ...(await knowledgeApi.uploadDocument(agentId.value, uploadList[0])),
          }],
        }
      : await knowledgeApi.uploadDocuments(agentId.value, uploadList)
    const newTasks = (result.items || []).map((item: any) => ({
        id: item.task_id,
        user_id: 0,
        agent_id: agentId.value,
        task_type: 'knowledge_index',
        status: item.status || 'queued',
        title: `文档入库: ${item.file_name}`,
        target_type: 'knowledge',
        target_id: item.knowledge_id,
        progress: 0,
        result: null,
        error_msg: null,
        retry_count: 0,
        parent_task_id: null,
        created_at: null,
        started_at: null,
        finished_at: null,
    }))
    tasks.value.unshift(...newTasks)
    await loadDocs()
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '上传失败')
  } finally {
    uploading.value = false
    uploadProgress.value = ''
  }
}

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  if (files.length) uploadFiles(files)
  target.value = ''
}

const handleDrop = (e: DragEvent) => {
  dragOver.value = false
  if (!canUseRag.value) return
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length) uploadFiles(files)
}

const handleDelete = async (doc: KnowledgeDoc) => {
  if (!confirm(`确认删除文档「${doc.file_name}」？相关知识块和向量也会删除。`)) return
  await knowledgeApi.deleteDocument(agentId.value, doc.id)
  await loadDocs()
}

const handleReindex = async (doc: KnowledgeDoc) => {
  if (!canUseRag.value) {
    uploadError.value = ragBlockedReason.value
    return
  }
  if (!confirm(`确认重新入库「${doc.file_name}」？旧向量和片段会被重建。`)) return
  reindexingId.value = doc.id
  uploadError.value = ''
  try {
    const result = await knowledgeApi.reindexDocument(agentId.value, doc.id)
    if (result?.task_id) {
      tasks.value.unshift({
        id: result.task_id,
        user_id: 0,
        agent_id: agentId.value,
        task_type: 'knowledge_reindex',
        status: result.status || 'queued',
        title: `重建索引: ${doc.file_name}`,
        target_type: 'knowledge',
        target_id: doc.id,
        progress: 0,
        result: null,
        error_msg: null,
        retry_count: 0,
        parent_task_id: null,
        created_at: null,
        started_at: null,
        finished_at: null,
      })
    }
    await loadDocs()
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '重新入库失败')
    await loadDocs()
  } finally {
    reindexingId.value = null
  }
}

const handleToggleEnabled = async (doc: KnowledgeDoc) => {
  const next = doc.is_enabled === 1 ? 0 : 1
  togglingEnabledId.value = doc.id
  uploadError.value = ''
  try {
    await knowledgeApi.updateDocumentEnabled(agentId.value, doc.id, next)
    doc.is_enabled = next
    if (selectedKnowledgeId.value === doc.id && next === 0) {
      selectedKnowledgeId.value = 0
    }
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '更新文档状态失败')
  } finally {
    togglingEnabledId.value = null
  }
}

const handleSearch = async () => {
  const q = searchQuery.value.trim()
  if (!q || searching.value) return
  if (!canUseRag.value) {
    searchError.value = ragBlockedReason.value
    return
  }
  searching.value = true
  searchingSlow.value = false
  window.clearTimeout(searchSlowTimer)
  searchSlowTimer = window.setTimeout(() => {
    searchingSlow.value = true
  }, 8000)
  hasSearched.value = true
  searchError.value = ''
  searchResults.value = []
  try {
    searchResults.value = await knowledgeApi.searchKnowledge(agentId.value, {
      query: q,
      top_k: topK.value,
      knowledge_id: selectedKnowledgeId.value || null,
    })
  } catch (e: any) {
    searchError.value = getErrorMessage(e, '检索失败')
  } finally {
    searching.value = false
    searchingSlow.value = false
    window.clearTimeout(searchSlowTimer)
  }
}

const openChunks = async (doc: KnowledgeDoc) => {
  chunkDoc.value = doc
  showChunks.value = true
  chunksLoading.value = true
  chunks.value = []
  try {
    chunks.value = await knowledgeApi.listChunks(agentId.value, doc.id)
  } catch (e: any) {
    searchError.value = getErrorMessage(e, '读取片段失败')
    showChunks.value = false
  } finally {
    chunksLoading.value = false
  }
}

const closeChunks = () => {
  showChunks.value = false
  chunkDoc.value = null
  chunks.value = []
}

const fileIcon = (type: string) => {
  if (type === 'pdf') return File
  return FileText
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const formatScore = (score: number) => {
  if (score >= 0 && score <= 1) return `${(score * 100).toFixed(1)}%`
  return score.toFixed(4)
}

const statusText = (s: string) => ({
  pending: '待处理',
  processing: '处理中',
  done: '已完成',
  failed: '失败',
}[s] || s)

const statusClass = (s: string) => ({
  pending: 'bg-slate-100 text-slate-600',
  processing: 'bg-blue-50 text-blue-700',
  done: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}[s] || 'bg-slate-100 text-slate-600')

const taskStatusText = (s: string) => ({
  queued: '排队中',
  running: '处理中',
  finished: '已完成',
  failed: '失败',
}[s] || s)

const taskStatusClass = (s: string) => ({
  queued: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-50 text-blue-700',
  finished: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}[s] || 'bg-slate-100 text-slate-600')

onMounted(loadPage)
onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
  if (searchSlowTimer !== undefined) window.clearTimeout(searchSlowTimer)
  if (taskPollTimer !== undefined) window.clearInterval(taskPollTimer)
})
watch(agentId, async () => {
  selectedKnowledgeId.value = 0
  searchResults.value = []
  searchError.value = ''
  hasSearched.value = false
  closeChunks()
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
  if (taskPollTimer !== undefined) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = undefined
  }
  tasks.value = []
  await loadPage()
})
</script>
