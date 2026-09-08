<template>
  <div class="h-full overflow-auto p-1">
    <p v-if="error" class="p-3 text-sm text-red-600">{{ error }}</p>
    <table v-else-if="rows.length" class="w-full text-left text-xs">
      <thead>
        <tr class="border-b border-sky-100 text-slate-500">
          <th v-for="col in columns" :key="col" class="px-2 py-1.5 font-medium">{{ col }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i" class="border-b border-sky-50 last:border-0">
          <td v-for="col in columns" :key="col" class="px-2 py-1.5 text-slate-700">{{ formatCell(row[col]) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="p-3 text-sm text-slate-400">还没有数据，点一下“刷新”试试。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const rows = computed<Record<string, any>[]>(() => {
  const r = props.result
  if (!r) return []
  const list = Array.isArray(r) ? r : r.rows || r.items || r.points || []
  return list.filter((x: any) => x && typeof x === 'object')
})

const columns = computed<string[]>(() => {
  const configured = props.widget.view?.config?.columns
  if (Array.isArray(configured) && configured.length) return configured
  const first = rows.value[0] || {}
  return Object.keys(first).slice(0, 8)
})

function formatCell(v: any): string {
  if (v == null) return '—'
  if (typeof v === 'number') return v.toLocaleString()
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
</script>
