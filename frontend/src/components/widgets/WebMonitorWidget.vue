<template>
  <div class="flex h-full flex-col p-4">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <template v-else-if="hasContent">
      <div class="flex items-center justify-between gap-2">
        <span
          class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
          :class="statusClass"
        >
          {{ statusText }}
        </span>
        <a
          v-if="url"
          :href="url"
          target="_blank"
          rel="noopener noreferrer"
          class="truncate text-[11px] text-sky-600 hover:underline"
        >{{ hostText }}</a>
      </div>
      <p v-if="title" class="mt-2 truncate text-sm font-medium text-slate-800">{{ title }}</p>
      <p class="mt-1 flex-1 overflow-hidden whitespace-pre-wrap text-sm leading-relaxed text-slate-600">{{ snippet }}</p>
      <p class="mt-2 text-[11px] text-slate-400">
        <span v-if="fetchedAt">抓取于 {{ fetchedAt }}</span>
        <span v-if="truncated"> · 已截取部分正文</span>
      </p>
    </template>
    <div v-else class="rounded border border-dashed border-sky-200 bg-sky-50/60 p-3 text-xs text-slate-500">
      还没有抓到内容，点右上角刷新试试。
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const r = computed<any>(() => props.result || null)
const hasContent = computed(() => !!r.value && (typeof r.value === 'string' || r.value.text || r.value.summary || r.value.content))

const snippet = computed<string>(() => {
  const v = r.value
  if (!v) return ''
  if (typeof v === 'string') return v
  return v.text || v.summary || v.content || ''
})
const title = computed<string>(() => (r.value && typeof r.value === 'object' ? r.value.title || '' : ''))
const url = computed<string>(() => (r.value && typeof r.value === 'object' ? r.value.url || '' : ''))
const hostText = computed<string>(() => {
  if (!url.value) return ''
  try {
    return new URL(url.value).host
  } catch {
    return url.value
  }
})
const fetchedAt = computed<string>(() => (r.value && typeof r.value === 'object' ? r.value.fetched_at || '' : ''))
const truncated = computed<boolean>(() => !!(r.value && typeof r.value === 'object' && r.value.truncated))

const isMonitor = computed(() => r.value && typeof r.value === 'object' && r.value.mode === 'monitor')
const statusText = computed(() => {
  if (!isMonitor.value) return '最新内容'
  if (r.value.first_seen) return '已开始监控'
  return r.value.changed ? '内容有更新' : '暂无变化'
})
const statusClass = computed(() => {
  if (isMonitor.value && r.value.changed) return 'bg-amber-100 text-amber-700'
  if (isMonitor.value && !r.value.first_seen) return 'bg-emerald-100 text-emerald-700'
  return 'bg-slate-100 text-slate-600'
})
</script>
