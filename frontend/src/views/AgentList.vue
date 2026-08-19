<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <div>
        <h1 class="text-base font-semibold text-slate-900">我的 Agent</h1>
        <p class="text-xs text-slate-500">{{ agents.length }} 个 Agent，{{ selectedAgentName || '未选择默认 Agent' }}</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="router.push('/llm-configs')"
          class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <Cpu :size="15" />
          模型配置
        </button>
        <button
          @click="router.push('/skills')"
          class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <Zap :size="15" />
          Skill 管理
        </button>
        <button
          @click="router.push('/tasks')"
          class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <ListChecks :size="15" />
          后台任务
        </button>
        <button
          @click="openCreateDialog"
          class="inline-flex items-center gap-2 rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus :size="15" />
          新建 Agent
        </button>
        <div class="ml-3 flex items-center gap-2 border-l border-slate-200 pl-3">
          <span class="max-w-28 truncate text-sm text-slate-600">{{ userStore.user?.name }}</span>
          <button
            @click="userStore.logout"
            class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
            title="退出登录"
          >
            <LogOut :size="15" />
          </button>
        </div>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-6">
      <div class="mx-auto max-w-7xl">
        <div v-if="loading" class="py-20 text-center text-sm text-slate-500">加载中...</div>

        <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          <div class="flex items-center justify-between gap-3">
            <span>{{ loadError }}</span>
            <button @click="reload" class="shrink-0 rounded border border-red-200 bg-white px-3 py-1.5 text-xs hover:bg-red-100">
              重试
            </button>
          </div>
        </div>

        <div v-else-if="agents.length === 0" class="rounded-lg border border-dashed border-slate-300 bg-white py-16 text-center">
          <Bot :size="34" class="mx-auto mb-3 text-slate-300" />
          <p class="text-sm font-medium text-slate-700">还没有 Agent</p>
          <p class="mt-1 text-sm text-slate-500">先创建一个 Agent，再配置模型、知识库和 Skill。</p>
          <button
            @click="openCreateDialog"
            class="mt-5 inline-flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus :size="15" />
            新建 Agent
          </button>
        </div>

        <div v-else class="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="agent in agents"
            :key="agent.id"
            class="bg-white border border-slate-200 rounded-lg p-4 hover:border-slate-300 hover:shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded bg-blue-50 text-blue-700">
                    <Bot :size="18" />
                  </span>
                  <div class="min-w-0">
                    <h2 class="truncate text-sm font-semibold text-slate-900">{{ agent.name }}</h2>
                    <p class="truncate text-xs text-slate-500">{{ agent.model_name }} · 温度 {{ agent.temperature }}</p>
                  </div>
                </div>
              </div>
              <span
                v-if="agent.is_selected"
                class="shrink-0 rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
              >
                默认
              </span>
            </div>

            <div class="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div class="rounded border border-slate-100 px-2 py-2">
                <span class="text-slate-400">模型 Key</span>
                <p :class="hasModelKey(agent.model_name || '') ? 'text-emerald-700' : 'text-amber-600'" class="mt-1 font-medium">
                  {{ hasModelKey(agent.model_name || '') ? '已配置' : '待配置' }}
                </p>
              </div>
              <div class="rounded border border-slate-100 px-2 py-2">
                <span class="text-slate-400">RAG</span>
                <p :class="ragStatusClass(agent)" class="mt-1 font-medium">
                  {{ ragStatusText(agent) }}
                </p>
              </div>
            </div>

            <div class="mt-4 min-h-7">
              <div v-if="agent.skills?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="skill in agent.skills"
                  :key="skill.id"
                  class="rounded bg-violet-50 px-2 py-1 text-xs text-violet-700"
                >
                  {{ skill.name }}
                </span>
              </div>
              <span v-else class="text-xs text-slate-400">未绑定 Skill</span>
            </div>

            <div class="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
              <div class="flex gap-1">
                <button
                  @click="enterChat(agent.id)"
                  :disabled="!hasModelKey(agent.model_name || '') || (agent.rag_enabled === 1 && !hasEmbeddingKey)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-blue-50 hover:text-blue-700"
                  title="聊天"
                >
                  <MessageSquare :size="15" />
                </button>
                <button
                  @click="router.push(`/knowledge/${agent.id}`)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-emerald-50 hover:text-emerald-700"
                  title="知识库"
                >
                  <BookOpen :size="15" />
                </button>
                <button
                  @click="router.push(`/agents/${agent.id}/debug`)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-amber-50 hover:text-amber-700"
                  title="调试"
                >
                  <Bug :size="15" />
                </button>
                <button
                  v-if="!hasModelKey(agent.model_name || '') || (agent.rag_enabled === 1 && !hasEmbeddingKey)"
                  @click="router.push('/llm-configs')"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-amber-500 hover:bg-amber-50 hover:text-amber-700"
                  title="配置模型 Key"
                >
                  <KeyRound :size="15" />
                </button>
                <button
                  @click="openEditDialog(agent)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  title="编辑"
                >
                  <Pencil :size="15" />
                </button>
                <button
                  @click="handleDelete(agent)"
                  class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-red-50 hover:text-red-600"
                  title="删除"
                >
                  <Trash2 :size="15" />
                </button>
              </div>
              <button
                @click="selectAgent(agent)"
                :disabled="agent.is_selected || selectingId === agent.id"
                class="rounded border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:border-transparent disabled:text-slate-300"
              >
                {{ agent.is_selected ? '已默认' : selectingId === agent.id ? '设置中...' : '设为默认' }}
              </button>
            </div>
          </article>
        </div>
      </div>
    </main>

    <AgentCreateDialog
      v-if="showCreateDialog"
      :agent="editingAgent"
      :skills="availableSkills"
      @close="closeDialog"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  BookOpen, Bot, Bug, Cpu, KeyRound, ListChecks, LogOut, MessageSquare, Pencil, Plus, Trash2, Zap,
} from 'lucide-vue-next'
import { useUserStore } from '../stores/user'
import * as agentApi from '../api/agent'
import type { AgentInfo } from '../api/agent'
import * as llmConfigApi from '../api/llmConfig'
import type { LlmConfig } from '../api/llmConfig'
import * as skillApi from '../api/skill'
import AgentCreateDialog from '../components/AgentCreateDialog.vue'
import { toastError } from '../utils/toast'
import { getErrorMessage } from '../utils/request'

const userStore = useUserStore()
const router = useRouter()

const agents = ref<AgentInfo[]>([])
const availableSkills = ref<any[]>([])
const configs = ref<LlmConfig[]>([])
const showCreateDialog = ref(false)
const editingAgent = ref<AgentInfo | null>(null)
const loading = ref(false)
const loadError = ref('')
const selectingId = ref<number | null>(null)

const selectedAgentName = computed(() => agents.value.find(a => a.is_selected)?.name || '')
const configuredModelNames = computed(() => new Set(configs.value.map((config) => config.model_name.toLowerCase())))
const hasEmbeddingKey = computed(() => configs.value.some((config) => {
  const model = config.model_name.toLowerCase()
  return model.includes('embedding') || model.startsWith('baai/') || model === 'glm-4'
}))

const hasModelKey = (modelName: string) => {
  return configuredModelNames.value.has(modelName.trim().toLowerCase())
}

const ragStatusText = (agent: AgentInfo) => {
  if (agent.rag_enabled !== 1) return '未启用'
  return hasEmbeddingKey.value ? '已启用' : '缺少 Key'
}

const ragStatusClass = (agent: AgentInfo) => {
  if (agent.rag_enabled !== 1) return 'text-slate-500'
  return hasEmbeddingKey.value ? 'text-emerald-700' : 'text-amber-600'
}

const reload = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const [agentList, userSkills, publicSkills, llmConfigs] = await Promise.all([
      agentApi.listAgents(),
      skillApi.listUserSkills(),
      skillApi.listPublicSkills(),
      llmConfigApi.listConfigs(),
    ])
    agents.value = agentList
    configs.value = llmConfigs
    const merged = new Map<number, any>()
    ;[...userSkills, ...publicSkills].forEach((s: any) => merged.set(s.id, s))
    availableSkills.value = [...merged.values()]
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '加载 Agent 列表失败')
  } finally {
    loading.value = false
  }
}

const enterChat = (agentId: number) => {
  router.push(`/chat/${agentId}`)
}

const openCreateDialog = () => {
  editingAgent.value = null
  showCreateDialog.value = true
}

const openEditDialog = (agent: AgentInfo) => {
  editingAgent.value = agent
  showCreateDialog.value = true
}

const closeDialog = () => {
  showCreateDialog.value = false
  editingAgent.value = null
}

const handleDialogSuccess = async (payload?: { agentId?: number; created: boolean }) => {
  if (payload?.created && payload.agentId) {
    await agentApi.selectAgent(payload.agentId)
    if (userStore.user) {
      userStore.user.selected_agent_id = payload.agentId
      localStorage.setItem('user', JSON.stringify(userStore.user))
    }
  }
  await reload()
}

const selectAgent = async (agent: AgentInfo) => {
  selectingId.value = agent.id
  try {
    await agentApi.selectAgent(agent.id)
    if (userStore.user) {
      userStore.user.selected_agent_id = agent.id
      localStorage.setItem('user', JSON.stringify(userStore.user))
    }
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '设置默认 Agent 失败'))
  } finally {
    selectingId.value = null
  }
}

const handleDelete = async (agent: AgentInfo) => {
  try {
    const preview = await agentApi.deletePreview(agent.id)
    const text = [
      `确认删除 Agent「${preview.agent_name}」？`,
      '',
      `会话：${preview.conversation_count}`,
      `消息：${preview.message_count}`,
      `知识库文档：${preview.knowledge_count}`,
      `运行记录：${preview.run_count}`,
      `Skill 绑定：${preview.skill_binding_count}`,
      '',
      '此操作不可恢复。',
    ].join('\n')
    if (!confirm(text)) return
    await agentApi.deleteAgent(agent.id)
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '删除失败'))
  }
}

onMounted(reload)
</script>
