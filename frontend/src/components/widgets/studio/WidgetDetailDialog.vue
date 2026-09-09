<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8" @click.self="emit('close')">
    <div class="flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
      <div class="flex items-center justify-between border-b border-sky-100 px-5 py-3">
        <h3 class="text-sm font-semibold text-slate-900">{{ widget.name }}</h3>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600"><X :size="16" /></button>
      </div>

      <div class="min-h-0 flex-1 overflow-auto p-5">
        <dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-slate-600">
          <div class="flex gap-2"><dt class="text-slate-400">数据从哪来</dt><dd>{{ widget.friendly.data_from }}</dd></div>
          <div class="flex gap-2"><dt class="text-slate-400">系统会做</dt><dd>{{ widget.friendly.system_does }}</dd></div>
          <div class="flex gap-2"><dt class="text-slate-400">怎么展示</dt><dd>{{ widget.friendly.show_as }}</dd></div>
          <div class="flex gap-2"><dt class="text-slate-400">多久更新</dt><dd>{{ widget.friendly.update_every }}</dd></div>
          <div class="flex gap-2"><dt class="text-slate-400">上次运行</dt><dd>{{ widget.status.last_run_at || '—' }}（{{ statusLabel }}）</dd></div>
          <div class="flex gap-2"><dt class="text-slate-400">下次自动</dt><dd>{{ widget.status.next_run_at || '手动刷新' }}</dd></div>
        </dl>

        <div class="mt-4 overflow-hidden rounded border border-sky-100">
          <div class="border-b border-sky-100 bg-sky-50/60 px-3 py-1.5 text-[11px] text-slate-500">当前内容</div>
          <div class="h-56"><WidgetRenderer :widget="widget" /></div>
        </div>

        <div class="mt-4">
          <p class="mb-1.5 text-xs font-medium text-slate-600">运行历史（近 {{ series.length }} 次）</p>
          <div v-if="loading" class="py-6 text-center text-xs text-slate-400">加载中…</div>
          <div v-else-if="!series.length" class="py-6 text-center text-xs text-slate-400">还没有历史记录</div>
          <div v-else class="max-h-56 overflow-auto rounded border border-slate-100">
            <table class="w-full text-left text-xs">
              <thead class="sticky top-0 bg-slate-50 text-slate-400">
                <tr>
                  <th class="px-3 py-1.5 font-medium">时间</th>
                  <th class="px-3 py-1.5 font-medium">状态</th>
                  <th class="px-3 py-1.5 font-medium">结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(p, i) in seriesDesc" :key="i" class="border-t border-slate-100">
                  <td class="whitespace-nowrap px-3 py-1.5 text-slate-500">{{ p.recorded_at || '—' }}</td>
                  <td class="px-3 py-1.5">
                    <span :class="p.ok ? 'text-emerald-600' : 'text-red-500'">{{ p.ok ? '成功' : '失败' }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-slate-600">{{ p.label ?? (p.value ?? '—') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 border-t border-sky-100 px-5 py-3">
        <button @click="emit('run')" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">立即刷新</button>
        <button @click="emit('close')" class="sci-primary rounded px-3 py-1.5 text-xs font-medium text-white">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { getWidgetData, type WidgetItem, type WidgetSeriesPoint } from '../../../api/widget'
import WidgetRenderer from '../WidgetRenderer.vue'

const props = defineProps<{ widget: WidgetItem; reloadKey?: number }>()
const emit = defineEmits<{ (e: 'close' | 'run'): void }>()

const series = ref<WidgetSeriesPoint[]>([])
const loading = ref(false)
const seriesDesc = computed(() => [...series.value].reverse())

const statusLabel = computed(
  () => ({ ok: '成功', error: '失败', paused: '已暂停' }[props.widget.status.last_status || ''] || '未运行'),
)

async function load() {
  loading.value = true
  try {
    const res = await getWidgetData(props.widget.id, true)
    series.value = res.series || []
  } catch {
    series.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.widget.id, props.reloadKey], load, { immediate: true })
</script>
