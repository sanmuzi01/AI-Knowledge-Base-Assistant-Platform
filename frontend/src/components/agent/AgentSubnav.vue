<template>
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <div class="flex min-w-0 items-center gap-2">
      <button
        @click="router.push('/agents')"
        class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-black/[.06] hover:text-slate-900"
        title="返回工作台"
        aria-label="返回工作台"
      >
        <ChevronLeft :size="19" :stroke-width="2" />
      </button>
      <div class="min-w-0">
        <p class="truncate text-[14px] font-semibold tracking-[-0.012em] text-slate-900">{{ agentName || `助手 #${agentId}` }}</p>
        <p class="truncate text-[11px] text-slate-400">助手空间</p>
      </div>
    </div>

    <nav class="flex w-full gap-1 overflow-x-auto md:w-auto md:flex-wrap">
      <RouterLink
        v-for="t in tabs"
        :key="t.key"
        :to="`/agents/${agentId}/${t.key}`"
        :class="[
          'shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors',
          t.key === active
            ? 'bg-black/[.07] text-slate-900'
            : 'text-slate-500 hover:bg-black/[.045] hover:text-slate-900',
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
import { ChevronLeft } from 'lucide-vue-next'

defineProps<{
  agentId: number | string
  agentName?: string
  active: 'chat' | 'knowledge' | 'memory' | 'debug' | 'tools'
}>()

const router = useRouter()

const tabs = [
  { key: 'chat', label: '聊天' },
  { key: 'knowledge', label: '知识库' },
  { key: 'memory', label: '记忆' },
  { key: 'tools', label: '接口工具' },
  { key: 'debug', label: '运行检查' },
] as const
</script>
