<template>
  <div class="flex h-full flex-col">
    <div
      v-if="generatedAt || sourceText"
      class="flex items-center gap-2 border-b border-sky-100 px-4 py-1.5 text-[11px] text-slate-400"
    >
      <span v-if="generatedAt" class="inline-flex items-center gap-1">
        <Clock :size="11" /> {{ generatedAt }}
      </span>
      <span v-if="sourceText" class="truncate">· {{ sourceText }}</span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto p-4">
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      <template v-else-if="skipped">
        <p class="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700">
          未连接 AI 模型，无法自动总结。请在【连接模型】里启用一个聊天模型后刷新。
        </p>
        <pre v-if="rawPreview" class="mt-2 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-500">{{ rawPreview }}</pre>
      </template>
      <div v-else-if="html" class="prose-widget text-sm leading-relaxed text-slate-700" v-html="html"></div>
      <p v-else class="text-sm text-slate-400">还没有内容，点一下"刷新"试试。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../../utils/markdown'
import { Clock } from 'lucide-vue-next'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const r = computed<any>(() => props.result ?? null)
const skipped = computed(() => !!(r.value && typeof r.value === 'object' && r.value.skipped))
const rawPreview = computed<string>(() => (r.value && typeof r.value === 'object' ? r.value.raw_preview || '' : ''))

const generatedAt = computed<string>(() => {
  const p = props.widget.latest?.payload
  return (r.value && typeof r.value === 'object' && r.value.generated_at) || p?.generated_at || ''
})
const sourceText = computed<string>(() => {
  const src = props.widget.latest?.payload?.source
  if (!src) return ''
  return src.url || src.provider || ''
})

const text = computed<string>(() => {
  const v = r.value
  if (v == null) return ''
  if (typeof v === 'string') return v
  return v.text || v.summary || v.markdown || v.value || v.content || ''
})

// 内容可能来自 llm_summarize / 外部数据源，渲染前统一做一轮轻量清洗
const html = computed<string>(() => {
  if (!text.value) return ''
  return renderMarkdown(String(text.value))
})
</script>

<style scoped>
.prose-widget :deep(h1),
.prose-widget :deep(h2),
.prose-widget :deep(h3) {
  font-weight: 600;
  margin: 0.9em 0 0.4em;
  color: #0f172a;
}
.prose-widget :deep(h2) {
  font-size: 0.95em;
}
.prose-widget :deep(p) {
  margin: 0.5em 0;
}
.prose-widget :deep(ul),
.prose-widget :deep(ol) {
  padding-left: 1.25em;
  margin: 0.4em 0;
}
.prose-widget :deep(ul) {
  list-style: disc;
}
.prose-widget :deep(ol) {
  list-style: decimal;
}
.prose-widget :deep(li) {
  margin: 0.2em 0;
}
.prose-widget :deep(strong) {
  color: #0f172a;
}
.prose-widget :deep(blockquote) {
  border-left: 3px solid #fbbf24;
  background: #fffbeb;
  margin: 0.6em 0;
  padding: 0.3em 0.7em;
  color: #92400e;
  border-radius: 0 4px 4px 0;
}
.prose-widget :deep(a) {
  color: #0284c7;
  text-decoration: underline;
}
.prose-widget :deep(code) {
  background: rgba(15, 23, 42, 0.06);
  padding: 0 4px;
  border-radius: 4px;
}
.prose-widget :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  font-size: 0.92em;
}
.prose-widget :deep(th),
.prose-widget :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 3px 8px;
}
</style>
