<template>
  <div class="flex h-full flex-col justify-center p-4" :class="levelBg">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <template v-else-if="hasValue">
      <p class="text-xs" :class="level ? 'font-medium' : 'text-slate-500'">{{ label }}</p>
      <p class="mt-1 text-3xl font-semibold" :class="levelText">
        {{ displayValue }}<span v-if="unit" class="ml-1 text-base font-normal text-slate-500">{{ unit }}</span>
      </p>
      <p v-if="alertText" class="mt-1.5 text-xs" :class="levelText">{{ alertText }}</p>
      <p v-else-if="delta !== null" class="mt-1 text-xs" :class="delta >= 0 ? 'text-emerald-600' : 'text-red-600'">
        {{ delta >= 0 ? '▲' : '▼' }} {{ Math.abs(delta) }} 较上次
      </p>
    </template>
    <p v-else class="text-sm text-slate-400">还没有数据，点一下“刷新”试试。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const num = computed<number | null>(() => {
  const r = props.result
  if (r == null) return props.widget.latest?.value ?? null
  if (typeof r === 'number') return r
  const v = r.value ?? r.summary?.runs ?? props.widget.latest?.value
  return typeof v === 'number' ? v : null
})
const hasValue = computed(() => num.value !== null)
const displayValue = computed(() => (num.value === null ? '—' : Number(num.value).toLocaleString()))
const delta = computed<number | null>(() => {
  const d = props.result?.delta
  return typeof d === 'number' ? d : null
})
const unit = computed(() => props.widget.view?.config?.unit || props.result?.unit || '')
const label = computed(() => props.widget.view?.config?.label || props.widget.latest?.label || '当前值')

// threshold_alert 处理器的产出
const level = computed<string>(() => (props.result && typeof props.result === 'object' ? props.result.level || '' : ''))
const alertText = computed<string>(() =>
  props.result && typeof props.result === 'object' && props.result.level && props.result.level !== 'ok'
    ? props.result.text || ''
    : '',
)
const levelBg = computed(() =>
  level.value === 'alert' ? 'bg-red-50' : level.value === 'warn' ? 'bg-amber-50' : '',
)
const levelText = computed(() =>
  level.value === 'alert' ? 'text-red-600' : level.value === 'warn' ? 'text-amber-600' : 'text-slate-950',
)
</script>
