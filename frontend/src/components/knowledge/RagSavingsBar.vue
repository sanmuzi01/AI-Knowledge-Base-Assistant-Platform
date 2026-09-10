<template>
  <div v-if="stats" :class="compact ? 'text-[11px]' : 'rounded-lg border border-slate-200 bg-slate-50 p-3'">
    <div class="flex items-center justify-between gap-2">
      <span :class="compact ? 'font-semibold text-amber-600' : 'text-xs font-semibold text-slate-700'">上下文压缩</span>
      <span
        class="rounded px-2 py-0.5 text-xs font-semibold"
        :class="savedPct >= 50 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'"
      >省 {{ savedPct }}%</span>
    </div>
    <div
      class="mt-1.5 grid gap-x-4 gap-y-1 text-[11px] text-slate-600"
      :class="compact ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-4'"
    >
      <div><span class="block text-slate-400">原文档字数</span>{{ fmtNum(stats.source_doc_chars) }}</div>
      <div><span class="block text-slate-400">召回片段</span>{{ stats.recall_chunks }} 条</div>
      <div><span class="block text-slate-400">送入上下文</span>{{ fmtNum(stats.context_chars) }} 字</div>
      <div><span class="block text-slate-400">估算省 Token</span>≈ {{ fmtNum(stats.est_tokens_saved) }}</div>
    </div>
    <div v-if="!compact" class="mt-2 h-1.5 overflow-hidden rounded bg-slate-200">
      <div class="h-full rounded bg-emerald-500" :style="{ width: savedPct + '%' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RagSavings } from '../../api/chat'

const props = defineProps<{ stats?: RagSavings | null; compact?: boolean }>()

const savedPct = computed(() => Math.round((props.stats?.saved_ratio ?? 0) * 100))
const fmtNum = (n: number) => (n >= 10000 ? (n / 10000).toFixed(1) + '万' : String(n ?? 0))
</script>
