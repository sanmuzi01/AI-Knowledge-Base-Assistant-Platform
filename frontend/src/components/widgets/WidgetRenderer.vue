<template>
  <div class="relative h-full">
    <!-- 数据其实是时间序列时，给一个「走势图 / 原始」切换 -->
    <div
      v-if="autoView"
      class="absolute right-2 top-2 z-10 flex overflow-hidden rounded-md border border-sky-200 bg-white/90 text-[11px] shadow-sm"
    >
      <button
        class="px-2 py-0.5"
        :class="mode === 'auto' ? 'bg-sky-500 text-white' : 'text-slate-500 hover:bg-sky-50'"
        @click="mode = 'auto'"
      >
        走势图
      </button>
      <button
        class="px-2 py-0.5"
        :class="mode === 'configured' ? 'bg-sky-500 text-white' : 'text-slate-500 hover:bg-sky-50'"
        @click="mode = 'configured'"
      >
        原始
      </button>
    </div>

    <component :is="viewComponent" :widget="activeWidget" :result="activeResult" :error="error" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { WidgetItem } from '../../api/widget'
import { resolveWidgetView } from './registry'

const props = defineProps<{ widget: WidgetItem }>()

const payload = computed<any>(() => props.widget.latest?.payload ?? null)
const result = computed(() => payload.value?.result ?? null)
const error = computed(() =>
  props.widget.latest && !props.widget.latest.ok ? props.widget.latest.error || '这次没取到数据' : '',
)

// 运行引擎在数据是时间序列、但用户选了非图表视图时给出的建议视图
const autoView = computed<any>(() => payload.value?.auto_view ?? null)
const mode = ref<'auto' | 'configured'>('auto')

const activeView = computed(() =>
  autoView.value && mode.value === 'auto' ? autoView.value : props.widget.view,
)
const viewComponent = computed(() => resolveWidgetView(activeView.value?.kind ?? props.widget.view_kind))

// 传给具体视图组件的 widget：切到 auto_view 时把 view / view_kind 一起换掉，ChartWidget 才能读到 chart_type
const activeWidget = computed<WidgetItem>(() => {
  if (autoView.value && mode.value === 'auto') {
    return { ...props.widget, view: autoView.value, view_kind: autoView.value.kind }
  }
  return props.widget
})
const activeResult = computed(() =>
  autoView.value && mode.value === 'auto' ? autoView.value.data ?? result.value : result.value,
)
</script>
