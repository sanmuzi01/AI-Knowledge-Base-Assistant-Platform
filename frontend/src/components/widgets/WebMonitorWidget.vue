<template>
  <div class="flex h-full flex-col justify-center p-4">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <template v-else-if="snapshot">
      <p class="text-xs text-slate-500">最近抓取内容</p>
      <p class="mt-1 line-clamp-6 whitespace-pre-wrap text-sm text-slate-700">{{ snapshot }}</p>
    </template>
    <div v-else class="rounded border border-dashed border-sky-200 bg-sky-50/60 p-3 text-xs text-slate-500">
      网页监控将在下个版本开放实时抓取。先保存了你的监控目标，等上线后会自动开始更新。
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const snapshot = computed<string>(() => {
  const r = props.result
  if (!r) return ''
  if (typeof r === 'string') return r
  return r.summary || r.text || r.content || ''
})
</script>
