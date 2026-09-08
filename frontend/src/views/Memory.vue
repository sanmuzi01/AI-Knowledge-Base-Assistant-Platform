<template>
  <div class="flex h-screen flex-col bg-transparent">
    <header class="flex h-16 items-center justify-between border-b border-sky-200/70 bg-white/78 px-6 shadow-lg shadow-sky-900/8 backdrop-blur-xl">
      <div class="flex min-w-0 items-center gap-3">
        <button
          @click="router.push('/agents')"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="返回工作台"
        >
          <ArrowLeft :size="16" />
        </button>
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold text-slate-900">长期记忆</h1>
          <p class="truncate text-xs text-slate-500">{{ currentAgent?.name || `助手 #${agentId}` }} 会长期记住的重要信息</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="loadData"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="刷新"
        >
          <RefreshCcw :size="15" />
        </button>
        <button
          @click="handleClear"
          :disabled="loading || memories.length === 0"
          class="inline-flex items-center gap-2 rounded border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Trash2 :size="15" />
          清空
        </button>
      </div>
    </header>

    <main class="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[380px_minmax(0,1fr)]">
      <section class="sci-panel m-5 rounded-lg p-5 lg:mr-0">
        <h2 class="text-sm font-semibold text-slate-800">添加记忆</h2>
        <p class="mt-1 text-xs text-slate-500">这些内容会在后续对话中提醒助手，帮助它更懂你的偏好和项目背景。</p>

        <div class="mt-5 space-y-4">
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-600">类型</span>
            <select
              v-model="form.memory_type"
              class="sci-field h-10 w-full rounded px-3 text-sm outline-none"
            >
              <option v-for="option in memoryTypes" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </label>

          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-600">内容</span>
            <textarea
              v-model="form.content"
              rows="8"
              class="sci-field w-full resize-none rounded px-3 py-2 text-sm leading-relaxed outline-none"
              placeholder="例如：用户偏好简洁回答；当前项目是 AI 助手工作台；用户希望每完成一项等待确认。"
            />
          </label>

          <button
            @click="handleCreate"
            :disabled="saving || !form.content.trim()"
            class="sci-primary inline-flex w-full items-center justify-center gap-2 rounded px-4 py-2 text-sm font-medium text-white disabled:bg-blue-300 disabled:shadow-none"
          >
            <Plus :size="15" />
            {{ saving ? '保存中...' : '添加记忆' }}
          </button>
        </div>

        <div class="mt-6 rounded border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
          系统会自动总结常用信息；你也可以手动添加“事实、偏好、备注”，直接控制助手应该长期记住什么。
        </div>
      </section>

      <section class="flex min-h-0 flex-col p-5">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <h2 class="text-sm font-semibold text-slate-800">记忆列表</h2>
            <p class="mt-1 text-xs text-slate-500">{{ memories.length }} 条记忆</p>
          </div>
          <div class="flex rounded border border-slate-200 bg-white p-1">
            <button
              v-for="filter in filters"
              :key="filter.value"
              @click="activeFilter = filter.value"
              :class="activeFilter === filter.value ? 'bg-sky-100 text-sky-800 ring-1 ring-sky-200' : 'text-slate-500 hover:bg-sky-50'"
              class="rounded px-3 py-1.5 text-xs"
            >
              {{ filter.label }}
            </button>
          </div>
        </div>

        <div v-if="loading" class="flex flex-1 items-center justify-center rounded border border-dashed border-sky-300/70 bg-white/62 text-sm text-slate-500 backdrop-blur">
          加载中...
        </div>

        <div v-else-if="loadError" class="flex flex-1 items-center justify-center rounded border border-red-200 bg-red-50 px-6 text-center text-sm text-red-700">
          {{ loadError }}
        </div>

        <div v-else-if="filteredMemories.length === 0" class="flex flex-1 items-center justify-center rounded border border-dashed border-sky-300/70 bg-white/62 px-6 text-center text-sm text-slate-500 backdrop-blur">
          暂无匹配记忆。可以手动添加，或多聊几轮后由系统自动总结。
        </div>

        <div v-else class="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          <article v-for="memory in filteredMemories" :key="memory.id" class="sci-panel rounded-lg p-4 transition hover:border-sky-300">
            <div v-if="editingId !== memory.id" class="space-y-3">
              <div class="flex items-start justify-between gap-3">
                <div class="flex min-w-0 items-center gap-2">
                  <span :class="typeClass(memory.memory_type)" class="rounded px-2 py-1 text-xs font-medium">
                    {{ typeLabel(memory.memory_type) }}
                  </span>
                  <span class="truncate text-xs text-slate-400">
                    {{ memory.created_at || '无创建时间' }}
                  </span>
                  <span v-if="memory.chat_count > 0" class="text-xs text-slate-400">
                    {{ memory.chat_count }} 轮
                  </span>
                </div>
                <div class="flex shrink-0 items-center gap-1">
                  <button
                    @click="startEdit(memory)"
                    class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                    title="编辑"
                  >
                    <Pencil :size="15" />
                  </button>
                  <button
                    @click="handleDelete(memory)"
                    class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除"
                  >
                    <Trash2 :size="15" />
                  </button>
                </div>
              </div>
              <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ memory.content }}</p>
            </div>

            <div v-else class="space-y-3">
              <select
                v-model="editForm.memory_type"
                class="sci-field h-9 rounded px-3 text-sm outline-none"
              >
                <option v-for="option in memoryTypes" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <textarea
                v-model="editForm.content"
                rows="6"
                class="sci-field w-full resize-none rounded px-3 py-2 text-sm leading-relaxed outline-none"
              />
              <div class="flex justify-end gap-2">
                <button
                  @click="cancelEdit"
                  class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
                >
                  <X :size="15" />
                  取消
                </button>
                <button
                  @click="handleUpdate(memory)"
                  :disabled="saving || !editForm.content.trim()"
                  class="sci-primary inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm text-white disabled:bg-slate-400 disabled:shadow-none"
                >
                  <Save :size="15" />
                  保存
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Pencil, Plus, RefreshCcw, Save, Trash2, X } from 'lucide-vue-next'
import * as agentApi from '../api/agent'
import type { AgentInfo } from '../api/agent'
import * as memoryApi from '../api/memory'
import type { MemoryItem } from '../api/memory'
import { toastSuccess } from '../utils/toast'
import { getErrorMessage } from '../utils/request'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => Number(route.params.agentId))
const currentAgent = ref<AgentInfo | null>(null)
const memories = ref<MemoryItem[]>([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const editingId = ref<number | null>(null)
const activeFilter = ref('all')

const form = reactive({
  memory_type: 'fact',
  content: '',
})

const editForm = reactive({
  memory_type: 'fact',
  content: '',
})

const memoryTypes = [
  { value: 'summary', label: '摘要' },
  { value: 'fact', label: '事实' },
  { value: 'preference', label: '偏好' },
  { value: 'note', label: '备注' },
]

const filters = [
  { value: 'all', label: '全部' },
  ...memoryTypes,
]

const filteredMemories = computed(() => {
  if (activeFilter.value === 'all') return memories.value
  return memories.value.filter((memory) => memory.memory_type === activeFilter.value)
})

const loadData = async () => {
  if (!agentId.value) return
  loading.value = true
  loadError.value = ''
  try {
    const [agent, items] = await Promise.all([
      agentApi.getAgent(agentId.value),
      memoryApi.listMemories(agentId.value),
    ])
    currentAgent.value = agent
    memories.value = items
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '读取长期记忆失败')
    memories.value = []
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!form.content.trim()) return
  saving.value = true
  try {
    await memoryApi.createMemory(agentId.value, {
      memory_type: form.memory_type,
      content: form.content.trim(),
    })
    form.content = ''
    await loadData()
    toastSuccess('记忆已添加')
  } finally {
    saving.value = false
  }
}

const startEdit = (memory: MemoryItem) => {
  editingId.value = memory.id
  editForm.memory_type = memory.memory_type
  editForm.content = memory.content
}

const cancelEdit = () => {
  editingId.value = null
  editForm.memory_type = 'fact'
  editForm.content = ''
}

const handleUpdate = async (memory: MemoryItem) => {
  if (!editForm.content.trim()) return
  saving.value = true
  try {
    await memoryApi.updateMemory(memory.id, {
      memory_type: editForm.memory_type,
      content: editForm.content.trim(),
    })
    cancelEdit()
    await loadData()
    toastSuccess('记忆已更新')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (memory: MemoryItem) => {
  if (!confirm('确认删除这条记忆？')) return
  await memoryApi.deleteMemory(memory.id)
  await loadData()
  toastSuccess('记忆已删除')
}

const handleClear = async () => {
  if (!confirm('确认清空该助手的全部长期记忆？')) return
  await memoryApi.clearMemories(agentId.value)
  cancelEdit()
  await loadData()
  toastSuccess('长期记忆已清空')
}

const typeLabel = (type: string) => memoryTypes.find((item) => item.value === type)?.label || type

const typeClass = (type: string) => {
  if (type === 'summary') return 'bg-blue-50 text-blue-700'
  if (type === 'preference') return 'bg-emerald-50 text-emerald-700'
  if (type === 'note') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-100 text-slate-700'
}

onMounted(loadData)
watch(agentId, () => {
  cancelEdit()
  loadData()
})
</script>
