<template>
  <div class="h-full overflow-auto p-4">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <template v-else-if="stats">
      <div v-if="healthScore !== null" class="mb-3">
        <div class="flex items-center justify-between text-xs text-slate-500">
          <span>整体健康度</span><span class="font-semibold text-slate-800">{{ healthScore }}</span>
        </div>
        <div class="mt-1 h-1.5 rounded bg-sky-100">
          <div class="h-1.5 rounded bg-sky-500" :style="{ width: `${healthScore}%` }"></div>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div v-for="tile in tiles" :key="tile.label" class="rounded border border-sky-100 bg-white/70 px-2.5 py-2">
          <p class="text-[11px] text-slate-500">{{ tile.label }}</p>
          <p class="mt-0.5 text-lg font-semibold text-slate-900">{{ tile.value }}</p>
        </div>
      </div>
    </template>
    <p v-else class="text-sm text-slate-400">还没有数据，点一下“刷新”试试。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const stats = computed(() => props.result || null)
const healthScore = computed<number | null>(() => {
  const s = stats.value?.health_score ?? stats.value?.status?.health_score
  return typeof s === 'number' ? s : null
})

const LABELS: Record<string, string> = {
  agents: '助手数',
  ready_agents: '可用助手',
  conversations: '会话数',
  messages: '消息数',
  runs: '运行次数',
  tasks: '后台任务',
  knowledge_docs: '资料条数',
  skills: '技能数',
  memories: '长期记忆',
  tokens: '累计 Token',
}

const tiles = computed(() => {
  const counts = stats.value?.counts || stats.value?.summary || {}
  return Object.entries(counts)
    .filter(([, v]) => typeof v === 'number')
    .map(([k, v]) => ({ label: LABELS[k] || k, value: Number(v).toLocaleString() }))
    .slice(0, 9)
})
</script>
