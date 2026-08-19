<template>
  <div class="h-screen overflow-y-auto bg-slate-50 p-6">
    <div class="mx-auto max-w-6xl">
      <header class="mb-5 flex items-center justify-between gap-3">
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold text-slate-900">Agent 调试</h1>
          <p class="text-xs text-slate-500">{{ debug?.agent.name || `Agent #${agentId}` }} 的 Prompt、Skill、RAG 和工具装配状态</p>
        </div>
        <div class="flex shrink-0 gap-2">
          <button @click="router.push(`/chat/${agentId}`)" class="rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
            去聊天
          </button>
          <button @click="loadDebug" :disabled="loading" class="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-300">
            <RefreshCcw :size="15" :class="loading ? 'animate-spin' : ''" />
            刷新
          </button>
        </div>
      </header>

      <div v-if="loading && !debug" class="rounded-lg border border-slate-200 bg-white py-16 text-center text-sm text-slate-500">
        加载中...
      </div>
      <div v-else-if="errorMsg" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {{ errorMsg }}
      </div>

      <template v-else-if="debug">
        <section class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div :class="debug.readiness.model_configured ? okCard : warnCard">
            <p class="text-xs text-slate-500">模型 Key</p>
            <p class="mt-1 text-sm font-semibold">{{ debug.readiness.model_configured ? '已配置' : '缺少' }}</p>
          </div>
          <div :class="debug.readiness.rag_ready ? okCard : warnCard">
            <p class="text-xs text-slate-500">RAG</p>
            <p class="mt-1 text-sm font-semibold">{{ debug.agent.rag_enabled === 1 ? `${debug.readiness.knowledge_done_count}/${debug.readiness.knowledge_total_count} 文档可用` : '未启用' }}</p>
          </div>
          <div class="rounded-lg border border-slate-200 bg-white p-4">
            <p class="text-xs text-slate-500">Skill</p>
            <p class="mt-1 text-sm font-semibold">{{ debug.readiness.skill_count }} 个 / {{ debug.readiness.tool_count }} 个工具</p>
          </div>
          <div class="rounded-lg border border-slate-200 bg-white p-4">
            <p class="text-xs text-slate-500">模型参数</p>
            <p class="mt-1 text-sm font-semibold">{{ debug.agent.model_name }} · {{ debug.agent.temperature }}</p>
          </div>
        </section>

        <section class="mb-5 rounded-lg border border-slate-200 bg-white">
          <header class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <h2 class="text-sm font-semibold text-slate-900">最终 Prompt</h2>
            <button @click="copyText(debug.prompt.final_prompt)" class="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50">
              复制
            </button>
          </header>
          <pre class="max-h-[420px] overflow-auto whitespace-pre-wrap p-4 text-sm leading-relaxed text-slate-700">{{ debug.prompt.final_prompt }}</pre>
        </section>

        <section class="mb-5 rounded-lg border border-slate-200 bg-white">
          <header class="border-b border-slate-200 px-4 py-3">
            <h2 class="text-sm font-semibold text-slate-900">Dry Run</h2>
          </header>
          <div class="space-y-4 p-4">
            <div class="flex gap-2">
              <input
                v-model="dryRunMessage"
                class="h-10 flex-1 rounded border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
                placeholder="输入测试问题，不会调用模型，也不会写入会话"
                @keydown.enter="runDryRun"
              />
              <button
                @click="runDryRun"
                :disabled="dryRunLoading || !dryRunMessage.trim()"
                class="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-300"
              >
                {{ dryRunLoading ? '检查中...' : '运行检查' }}
              </button>
            </div>
            <p v-if="dryRunError" class="text-sm text-red-600">{{ dryRunError }}</p>

            <div v-if="dryRun" class="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <div class="rounded border border-slate-200 p-3">
                <p class="text-xs text-slate-500">最终 Prompt</p>
                <p class="mt-1 text-sm font-semibold text-slate-900">{{ dryRun.stats.final_prompt_chars }} 字</p>
              </div>
              <div class="rounded border border-slate-200 p-3">
                <p class="text-xs text-slate-500">Messages</p>
                <p class="mt-1 text-sm font-semibold text-slate-900">{{ dryRun.stats.message_count }} 条</p>
              </div>
              <div class="rounded border border-slate-200 p-3">
                <p class="text-xs text-slate-500">历史消息</p>
                <p class="mt-1 text-sm font-semibold text-slate-900">{{ dryRun.stats.history_message_count }} 条</p>
              </div>
              <div :class="dryRun.rag.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'" class="rounded border p-3">
                <p class="text-xs">RAG</p>
                <p class="mt-1 text-sm font-semibold">{{ dryRun.rag.enabled ? `${dryRun.rag.hit_count} 条命中` : '未启用' }}</p>
              </div>
            </div>

            <div v-if="dryRun" class="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <section class="rounded border border-slate-200">
                <header class="flex items-center justify-between border-b border-slate-200 px-3 py-2">
                  <h3 class="text-xs font-semibold text-slate-700">最终 Messages</h3>
                  <button @click="copyText(JSON.stringify(dryRun.messages, null, 2))" class="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-50">复制</button>
                </header>
                <div class="max-h-80 overflow-y-auto p-3">
                  <article v-for="(msg, idx) in dryRun.messages" :key="idx" class="mb-3 rounded bg-slate-50 p-3">
                    <p class="mb-1 text-xs font-semibold text-slate-500">{{ msg.role }}</p>
                    <p class="whitespace-pre-wrap text-xs leading-relaxed text-slate-700">{{ short(msg.content, 1200) }}</p>
                  </article>
                </div>
              </section>
              <section class="rounded border border-slate-200">
                <header class="border-b border-slate-200 px-3 py-2">
                  <h3 class="text-xs font-semibold text-slate-700">RAG 命中</h3>
                </header>
                <div class="max-h-80 overflow-y-auto p-3">
                  <p v-if="dryRun.rag.error" class="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{{ dryRun.rag.error }}</p>
                  <article v-for="(item, idx) in dryRun.rag.results" :key="idx" class="mb-3 rounded bg-slate-50 p-3">
                    <div class="mb-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                      <span class="truncate">{{ item.file_name || `片段 ${idx + 1}` }}</span>
                      <span v-if="typeof item.score === 'number'">{{ (item.score * 100).toFixed(1) }}%</span>
                    </div>
                    <p class="whitespace-pre-wrap text-xs leading-relaxed text-slate-700">{{ short(item.content, 800) }}</p>
                  </article>
                  <div v-if="!dryRun.rag.error && dryRun.rag.results.length === 0" class="py-8 text-center text-sm text-slate-400">没有命中片段</div>
                </div>
              </section>
            </div>
          </div>
        </section>

        <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <section class="rounded-lg border border-slate-200 bg-white">
            <header class="border-b border-slate-200 px-4 py-3">
              <h2 class="text-sm font-semibold text-slate-900">Skill 与工具</h2>
            </header>
            <div class="space-y-3 p-4">
              <div>
                <p class="mb-2 text-xs font-medium text-slate-500">工具列表</p>
                <div class="flex flex-wrap gap-1.5">
                  <span v-for="tool in debug.tool_names" :key="tool" class="rounded bg-blue-50 px-2 py-1 text-xs text-blue-700">{{ tool }}</span>
                  <span v-if="debug.tool_names.length === 0" class="text-xs text-slate-400">没有绑定工具</span>
                </div>
              </div>
              <article v-for="skill in debug.skills" :key="skill.name" class="rounded border border-slate-100 p-3">
                <h3 class="text-sm font-semibold text-slate-800">{{ skill.name }}</h3>
                <p class="mt-1 text-xs text-slate-500">{{ skill.description || '暂无描述' }}</p>
              </article>
            </div>
          </section>

          <section class="rounded-lg border border-slate-200 bg-white">
            <header class="border-b border-slate-200 px-4 py-3">
              <h2 class="text-sm font-semibold text-slate-900">运行时权限</h2>
            </header>
            <div class="space-y-3 p-4">
              <div class="flex flex-wrap gap-2">
                <span :class="debug.permissions?.network ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'" class="rounded px-2 py-1 text-xs">
                  网络 {{ debug.permissions?.network ? '允许' : '关闭' }}
                </span>
                <span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  资源 {{ debug.permissions?.file_read?.length || 0 }} 项
                </span>
                <span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  执行代码 关闭
                </span>
              </div>
              <div v-if="debug.resources?.length" class="max-h-60 overflow-y-auto space-y-2">
                <article v-for="resource in debug.resources" :key="`${resource.skill_name}-${resource.path}`" class="rounded border border-slate-100 p-3">
                  <div class="flex items-center justify-between gap-2">
                    <p class="truncate text-sm font-medium text-slate-800">{{ resource.path }}</p>
                    <span :class="resource.allowed ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'" class="shrink-0 rounded px-2 py-1 text-xs">
                      {{ resource.allowed ? '已授权' : '未授权' }}
                    </span>
                  </div>
                  <p class="mt-1 text-xs text-slate-400">{{ resource.skill_name || 'Skill' }} · {{ resource.exists ? `${resource.size} bytes` : '文件缺失' }}</p>
                </article>
              </div>
              <div v-else class="py-8 text-center text-sm text-slate-400">没有声明资源</div>
            </div>
          </section>

          <section class="rounded-lg border border-slate-200 bg-white">
            <header class="border-b border-slate-200 px-4 py-3">
              <h2 class="text-sm font-semibold text-slate-900">知识库</h2>
            </header>
            <div class="space-y-2 p-4">
              <article v-for="doc in debug.knowledge" :key="doc.id" class="rounded border border-slate-100 p-3">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <h3 class="truncate text-sm font-medium text-slate-800">{{ doc.file_name }}</h3>
                    <p class="mt-1 text-xs text-slate-500">{{ doc.chunk_count }} 块</p>
                    <p v-if="doc.error_msg" class="mt-1 line-clamp-2 text-xs text-red-600">{{ doc.error_msg }}</p>
                  </div>
                  <span :class="doc.status === 'done' ? 'bg-emerald-50 text-emerald-700' : doc.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'" class="shrink-0 rounded px-2 py-1 text-xs">
                    {{ doc.status }}
                  </span>
                </div>
              </article>
              <div v-if="debug.knowledge.length === 0" class="py-8 text-center text-sm text-slate-400">暂无知识库文档</div>
            </div>
          </section>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { RefreshCcw } from 'lucide-vue-next'
import * as agentApi from '../api/agent'
import type { AgentDebugInfo, AgentDryRunInfo } from '../api/agent'
import { toastSuccess } from '../utils/toast'
import { getErrorMessage } from '../utils/request'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => Number(route.params.agentId))
const debug = ref<AgentDebugInfo | null>(null)
const dryRun = ref<AgentDryRunInfo | null>(null)
const loading = ref(false)
const dryRunLoading = ref(false)
const errorMsg = ref('')
const dryRunError = ref('')
const dryRunMessage = ref('')

const okCard = 'rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-700'
const warnCard = 'rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-700'

const loadDebug = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    debug.value = await agentApi.getAgentDebug(agentId.value)
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '读取调试信息失败')
  } finally {
    loading.value = false
  }
}

const copyText = async (text: string) => {
  await navigator.clipboard.writeText(text)
  toastSuccess('已复制 Prompt')
}

const short = (text: string, max: number) => {
  return text.length > max ? `${text.slice(0, max)}...` : text
}

const runDryRun = async () => {
  const message = dryRunMessage.value.trim()
  if (!message || dryRunLoading.value) return
  dryRunLoading.value = true
  dryRunError.value = ''
  dryRun.value = null
  try {
    dryRun.value = await agentApi.dryRunAgent(agentId.value, { message })
  } catch (e: any) {
    dryRunError.value = getErrorMessage(e, 'Dry Run 失败')
  } finally {
    dryRunLoading.value = false
  }
}

onMounted(loadDebug)
watch(agentId, async () => {
  dryRun.value = null
  dryRunError.value = ''
  await loadDebug()
})
</script>
