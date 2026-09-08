<template>
  <div class="h-full w-full">
    <p v-if="error" class="p-4 text-sm text-red-600">{{ error }}</p>
    <p v-else-if="!hasData" class="p-4 text-sm text-slate-400">还没有数据，点一下“刷新”试试。</p>
    <div v-else ref="chartEl" class="h-full min-h-[200px] w-full"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { WidgetItem } from '../../api/widget'

echarts.use([LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()

const chartEl = ref<HTMLDivElement | null>(null)
let chart: ReturnType<typeof echarts.init> | null = null

// 把各种 result 结构收敛成 [{ name, value }]
const series = computed<{ name: string; value: number }[]>(() => {
  const r = props.result
  if (!r) return []
  const rows = Array.isArray(r) ? r : r.points || r.rows || []
  return rows
    .map((row: any) => {
      if (row == null) return null
      const name = row.t ?? row.date ?? row.name ?? row.label ?? ''
      const value = Number(row.y ?? row.value ?? row.count)
      return Number.isFinite(value) ? { name: String(name), value } : null
    })
    .filter(Boolean) as { name: string; value: number }[]
})

const hasData = computed(() => series.value.length > 0)
const chartType = computed(() => props.widget.view?.config?.chart_type || 'line')
const unit = computed(() => props.widget.view?.config?.unit || props.result?.unit || '')

function buildOption(): EChartsOption {
  const data = series.value
  if (chartType.value === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, type: 'scroll' },
      series: [{ type: 'pie', radius: ['40%', '68%'], data: data.map((d) => ({ name: d.name, value: d.value })) }],
    }
  }
  return {
    grid: { left: 44, right: 16, top: 24, bottom: 32 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => `${v}${unit.value ? ' ' + unit.value : ''}` },
    xAxis: { type: 'category', data: data.map((d) => d.name), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: chartType.value === 'bar' ? 'bar' : 'line',
        smooth: chartType.value === 'line',
        showSymbol: false,
        areaStyle: chartType.value === 'line' ? { opacity: 0.12 } : undefined,
        data: data.map((d) => d.value),
        itemStyle: { color: '#0ea5e9' },
      },
    ],
  }
}

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(buildOption(), true)
  chart.resize()
}

const onResize = () => chart?.resize()

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
watch(() => [props.result, props.widget.view], render, { deep: true })
</script>
