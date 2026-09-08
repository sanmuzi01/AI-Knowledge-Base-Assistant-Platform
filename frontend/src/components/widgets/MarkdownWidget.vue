<template>
  <div class="h-full overflow-auto p-4">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <div v-else-if="html" class="prose-widget text-sm text-slate-700" v-html="html"></div>
    <p v-else class="text-sm text-slate-400">还没有内容，点一下“刷新”试试。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const text = computed<string>(() => {
  const r = props.result
  if (r == null) return ''
  if (typeof r === 'string') return r
  return r.text || r.markdown || r.value || r.content || ''
})

// P1 的数据源都是服务端可控的内置/系统数据，先做轻量清洗；
// P2 接入 llm_summarize 后再补更严格的 HTML 消毒。
const html = computed<string>(() => {
  if (!text.value) return ''
  const raw = marked.parse(String(text.value), { async: false }) as string
  return raw
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/ on[a-z]+="[^"]*"/gi, '')
    .replace(/javascript:/gi, '')
})
</script>

<style scoped>
.prose-widget :deep(h1),
.prose-widget :deep(h2),
.prose-widget :deep(h3) {
  font-weight: 600;
  margin: 0.6em 0 0.3em;
}
.prose-widget :deep(ul) {
  list-style: disc;
  padding-left: 1.2em;
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
</style>
