<template>
  <div class="h-full overflow-auto p-3">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <ul v-else-if="items.length" class="space-y-1.5">
      <li
        v-for="(item, i) in items"
        :key="i"
        class="flex items-start gap-2 rounded border border-sky-100 bg-white/70 px-2.5 py-1.5 text-xs"
      >
        <span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full" :class="dotClass(item.status)"></span>
        <div class="min-w-0">
          <p class="truncate text-slate-800">{{ item.title || item.name || item.text || '未命名' }}</p>
          <p v-if="item.status || item.created_at" class="text-[11px] text-slate-400">
            {{ statusText(item.status) }}<span v-if="item.created_at"> · {{ item.created_at }}</span>
          </p>
        </div>
      </li>
    </ul>
    <p v-else class="text-sm text-slate-400">还没有条目，点一下“刷新”试试。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const items = computed<Record<string, any>[]>(() => {
  const r = props.result
  if (!r) return []
  const list = Array.isArray(r) ? r : r.items || r.rows || r.recent_tasks || r.tasks || []
  return list.filter((x: any) => x && typeof x === 'object')
})

const STATUS: Record<string, string> = {
  queued: '排队中',
  running: '进行中',
  finished: '已完成',
  failed: '失败',
  cancelled: '已取消',
  done: '已完成',
  pending: '待处理',
}
function statusText(s?: string) {
  return s ? STATUS[s] || s : ''
}
function dotClass(s?: string) {
  if (s === 'failed') return 'bg-red-500'
  if (s === 'finished' || s === 'done') return 'bg-emerald-500'
  if (s === 'running') return 'bg-sky-500'
  return 'bg-slate-300'
}
</script>
