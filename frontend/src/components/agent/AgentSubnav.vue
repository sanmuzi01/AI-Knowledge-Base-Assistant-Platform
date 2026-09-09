<template>
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <div class="flex min-w-0 items-center gap-2">
      <button
        @click="router.push('/agents')"
        class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
        title="返回工作台"
      >
        <ArrowLeft :size="15" />
      </button>
      <div class="min-w-0">
        <p class="truncate text-sm font-semibold text-slate-900">{{ agentName || `助手 #${agentId}` }}</p>
        <p class="truncate text-[11px] text-slate-400">助手空间</p>
      </div>
    </div>

    <nav class="flex flex-wrap gap-1">
      <RouterLink
        v-for="t in tabs"
        :key="t.key"
        :to="`/agents/${agentId}/${t.key}`"
        :class="[
          'rounded px-2.5 py-1.5 text-xs font-medium transition-colors',
          t.key === active
            ? 'bg-sky-100 text-sky-800 ring-1 ring-sky-200'
            : 'text-slate-600 hover:bg-sky-50 hover:text-slate-900',
        ]"
      >
        {{ t.label }}
      </RouterLink>
    </nav>

    <div v-if="$slots.actions" class="ml-auto flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'

defineProps<{
  agentId: number | string
  agentName?: string
  active: 'chat' | 'knowledge' | 'memory' | 'debug'
}>()

const router = useRouter()

const tabs = [
  { key: 'chat', label: '聊天' },
  { key: 'knowledge', label: '知识库' },
  { key: 'memory', label: '记忆' },
  { key: 'debug', label: '运行检查' },
] as const
</script>
