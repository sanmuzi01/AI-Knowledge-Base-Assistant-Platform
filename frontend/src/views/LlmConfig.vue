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
          <h1 class="text-base font-semibold text-slate-900">模型与 RAG Key 配置</h1>
          <p class="text-xs text-slate-500">聊天模型和知识库向量模型都使用当前用户自己保存的 API Key</p>
        </div>
      </div>
      <button
        @click="openCreate"
        class="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
      >
        <Plus :size="15" />
        新增配置
      </button>
    </header>

    <main class="flex-1 overflow-y-auto p-6">
      <div class="mx-auto grid max-w-6xl grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
        <section class="bg-white border border-slate-200 rounded-lg p-5">
          <h2 class="text-sm font-semibold text-slate-800 mb-4">{{ editingName ? '更新配置' : '新增配置' }}</h2>

          <div class="mb-4 grid grid-cols-2 gap-2">
            <button
              v-for="preset in presets"
              :key="preset.model"
              @click="applyPreset(preset)"
              class="rounded border border-slate-200 px-3 py-2 text-left hover:bg-slate-50"
            >
              <span class="block text-xs font-medium text-slate-800">{{ preset.label }}</span>
              <span class="block truncate text-xs text-slate-400">{{ preset.model }}</span>
            </button>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">用途</label>
              <select v-model="form.kind" class="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500">
                <option value="chat">聊天模型</option>
                <option value="embedding">RAG 向量模型</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">模型名称</label>
              <input
                v-model="form.model_name"
                list="model-options"
                class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
                placeholder="例如 glm-4 或 embedding-3"
              />
              <datalist id="model-options">
                <option v-for="m in modelOptions" :key="m" :value="m" />
              </datalist>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">API Key</label>
              <input
                v-model="form.api_key"
                type="password"
                class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
                placeholder="输入当前用户自己的 API Key"
              />
            </div>

            <div class="rounded bg-blue-50 px-3 py-2 text-xs leading-relaxed text-blue-800">
              只需要选择模型并填写 API Key，服务端会按模型名称自动适配官方 URL。RAG 会优先使用已配置的向量模型 Key。
            </div>

            <div class="flex items-center justify-end gap-2 pt-2">
              <button
                v-if="editingName"
                @click="resetForm"
                class="rounded border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                取消
              </button>
              <button
                @click="submit"
                :disabled="submitting || !form.model_name.trim() || !form.api_key.trim()"
                class="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-300"
              >
                {{ submitting ? '保存中...' : '保存' }}
              </button>
            </div>
            <p v-if="errorMsg" class="text-sm text-red-600">{{ errorMsg }}</p>
          </div>
        </section>

        <section class="min-w-0">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-slate-800">已配置</h2>
            <button @click="reload" class="text-xs text-slate-500 hover:text-slate-900">刷新</button>
          </div>

          <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <MessageSquare :size="16" />
                聊天模型 Key
              </div>
              <p class="mt-2 text-xs text-slate-500">Agent 对话时按 Agent 的模型名读取，例如 glm-4、deepseek-chat、gpt-4o。</p>
            </div>
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Database :size="16" />
                RAG 向量 Key
              </div>
              <p class="mt-2 text-xs text-slate-500">知识库上传和检索时读取 embedding-3 或 text-embedding-3-small 等向量模型配置。</p>
            </div>
          </div>

          <div v-if="configs.length === 0" class="rounded-lg border border-dashed border-slate-300 bg-white py-16 text-center text-sm text-slate-500">
            还没有模型配置。先添加聊天模型 Key，再添加 RAG 向量模型 Key。
          </div>

          <div v-else class="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <article
              v-for="cfg in configs"
              :key="cfg.id"
              class="bg-white border border-slate-200 rounded-lg p-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <component :is="isEmbeddingModel(cfg.model_name) ? Database : Cpu" :size="16" class="text-slate-500" />
                    <h3 class="truncate text-sm font-semibold text-slate-900">{{ cfg.model_name }}</h3>
                  </div>
                  <p class="mt-2 text-xs text-slate-500 font-mono">{{ cfg.api_key }}</p>
                  <p class="mt-1 truncate text-xs text-slate-400">{{ providerText(cfg.provider || providerOf(cfg.model_name)) }} · URL 自动适配</p>
                  <p
                    v-if="testResults[cfg.model_name]"
                    :class="testResults[cfg.model_name].ok ? 'text-emerald-700' : 'text-red-600'"
                    class="mt-2 text-xs"
                  >
                    {{ testResultText(testResults[cfg.model_name]) }}
                  </p>
                </div>
                <span
                  :class="isEmbeddingModel(cfg.model_name) ? 'bg-blue-50 text-blue-700' : 'bg-violet-50 text-violet-700'"
                  class="rounded px-2 py-1 text-xs"
                >
                  {{ isEmbeddingModel(cfg.model_name) ? 'RAG' : '聊天' }}
                </span>
              </div>
              <div class="mt-4 flex justify-end gap-2">
                <button
                  @click="testConfig(cfg)"
                  :disabled="testingName === cfg.model_name"
                  class="inline-flex h-8 items-center justify-center rounded border border-emerald-100 px-3 text-xs text-emerald-700 hover:bg-emerald-50 disabled:text-slate-300"
                  title="测试连接"
                >
                  {{ testingName === cfg.model_name ? '测试中...' : '测试' }}
                </button>
                <button
                  @click="editConfig(cfg)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50"
                  title="更新"
                >
                  <Pencil :size="14" />
                </button>
                <button
                  @click="removeConfig(cfg)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded border border-red-100 text-red-500 hover:bg-red-50"
                  title="删除"
                >
                  <Trash2 :size="14" />
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Cpu, Database, MessageSquare, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import * as llmApi from '../api/llmConfig'
import type { LlmConfig, LlmConfigTestResult, SupportedModel } from '../api/llmConfig'
import { getErrorMessage } from '../utils/request'
import { toastError, toastSuccess } from '../utils/toast'

const router = useRouter()
const configs = ref<LlmConfig[]>([])
const supportedCatalog = ref<{ chat: SupportedModel[]; embedding: SupportedModel[] }>({ chat: [], embedding: [] })
const submitting = ref(false)
const testingName = ref('')
const errorMsg = ref('')
const editingName = ref('')
const testResults = ref<Record<string, LlmConfigTestResult>>({})

const presets = [
  { kind: 'chat', label: '智谱聊天', model: 'glm-4' },
  { kind: 'embedding', label: '智谱 RAG', model: 'embedding-3' },
  { kind: 'chat', label: 'DeepSeek', model: 'deepseek-chat' },
  { kind: 'embedding', label: 'OpenAI RAG', model: 'text-embedding-3-small' },
]
const fallbackModels = ['glm-4', 'glm-4-plus', 'deepseek-chat', 'gpt-4o', 'gpt-4o-mini', 'embedding-3', 'embedding-2', 'text-embedding-3-small', 'text-embedding-3-large']
const modelOptions = computed(() => {
  const catalog = form.value.kind === 'embedding' ? supportedCatalog.value.embedding : supportedCatalog.value.chat
  return [...new Set([...catalog.map((item) => item.model_name), ...fallbackModels.filter((name) => form.value.kind === 'embedding' ? isEmbeddingModel(name) : !isEmbeddingModel(name))])]
})

const form = ref({
  kind: 'chat',
  model_name: '',
  api_key: '',
})

const isEmbeddingModel = (model: string) => {
  const m = model.toLowerCase()
  return m.includes('embedding') || m.startsWith('baai/')
}

const reload = async () => {
  configs.value = await llmApi.listConfigs()
}

const loadSupportedModels = async () => {
  try {
    supportedCatalog.value = await llmApi.listSupportedModelCatalog()
  } catch {
    supportedCatalog.value = { chat: [], embedding: [] }
  }
}

const resetForm = () => {
  editingName.value = ''
  form.value = { kind: 'chat', model_name: '', api_key: '' }
  errorMsg.value = ''
}

const openCreate = () => resetForm()

const applyPreset = (preset: typeof presets[number]) => {
  form.value.kind = preset.kind
  form.value.model_name = preset.model
}

const editConfig = (cfg: LlmConfig) => {
  editingName.value = cfg.model_name
  form.value = {
    kind: isEmbeddingModel(cfg.model_name) ? 'embedding' : 'chat',
    model_name: cfg.model_name,
    api_key: '',
  }
  errorMsg.value = ''
}

const submit = async () => {
  if (!form.value.model_name.trim() || !form.value.api_key.trim()) return
  submitting.value = true
  errorMsg.value = ''
  try {
    await llmApi.saveConfig({
      model_name: form.value.model_name.trim(),
      api_key: form.value.api_key.trim(),
    })
    await reload()
    resetForm()
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '保存失败')
  } finally {
    submitting.value = false
  }
}

const removeConfig = async (cfg: LlmConfig) => {
  if (!confirm(`确认删除模型配置「${cfg.model_name}」？使用该模型的功能将无法继续调用。`)) return
  await llmApi.deleteConfig(cfg.model_name)
  await reload()
  if (editingName.value === cfg.model_name) resetForm()
}

const testConfig = async (cfg: LlmConfig) => {
  testingName.value = cfg.model_name
  try {
    const result = await llmApi.testConfig(cfg.model_name)
    testResults.value[cfg.model_name] = result
    toastSuccess(`${cfg.model_name} 连接正常`)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    const result = typeof detail === 'object'
      ? detail as LlmConfigTestResult
      : {
          ok: false,
          model_name: cfg.model_name,
          message: getErrorMessage(e, '连接测试失败'),
        }
    testResults.value[cfg.model_name] = result
    toastError(testResultText(result))
  } finally {
    testingName.value = ''
  }
}

const testResultText = (result: LlmConfigTestResult) => {
  if (result.ok) {
    const elapsed = result.elapsed_ms !== undefined ? ` · ${result.elapsed_ms}ms` : ''
    if (result.kind === 'embedding') return `${result.message} · ${result.dimension || 0}维${elapsed}`
    return `${result.message}${elapsed}${result.preview ? ` · ${result.preview}` : ''}`
  }
  return `${result.message}${result.error ? `：${result.error}` : ''}`
}

onMounted(async () => {
  await Promise.all([reload(), loadSupportedModels()])
})

const providerOf = (modelName: string) => {
  const name = modelName.toLowerCase()
  if (name.startsWith('deepseek')) return 'deepseek'
  if (name.startsWith('gpt') || name.startsWith('text-embedding')) return 'openai'
  if (name.startsWith('baai/')) return 'local'
  return 'zhipu'
}

const providerText = (provider: string) => ({
  zhipu: '智谱',
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
  local: '本地模型',
}[provider] || provider)
</script>
