<template>
  <article
    draggable="true"
    @dragstart="emit('dragstart')"
    @dragover.prevent
    @drop="emit('drop')"
    @dragend="emit('dragend')"
    class="ui-card flex flex-col rounded-lg transition-shadow"
    :class="[{ 'opacity-60': !widget.enabled, 'opacity-40': dragging }, attentionRing]"
  >
    <div class="flex items-start justify-between gap-2 border-b border-sky-100 px-4 py-2.5">
      <div class="min-w-0">
        <p class="flex items-center gap-1.5 truncate text-sm font-medium text-slate-900">
          <span
            v-if="widget.attention"
            class="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
            :class="dotClass"
            :title="attentionLabel"
          ></span>
          {{ widget.name }}
        </p>
        <p class="truncate text-[11px] text-slate-400">
          {{ widget.friendly.data_from }} · {{ widget.friendly.update_every }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-1">
        <button @click="emit('run')" :disabled="running"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600 disabled:opacity-40" title="刷新">
          <RefreshCw :size="13" :class="{ 'animate-spin': running }" />
        </button>
        <button @click="emit('detail')"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600" title="详情与历史">
          <BarChart3 :size="13" />
        </button>
        <button @click="emit('export')"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600" title="导出配置">
          <Download :size="13" />
        </button>
        <button @click="emit('edit')"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600" title="编辑">
          <Pencil :size="13" />
        </button>
        <button @click="emit('toggle')"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600"
          :title="widget.enabled ? '隐藏' : '显示'">
          <EyeOff v-if="widget.enabled" :size="13" />
          <Eye v-else :size="13" />
        </button>
        <button @click="emit('delete')"
          class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600" title="删除">
          <Trash2 :size="13" />
        </button>
      </div>
    </div>

    <div class="min-h-[220px] flex-1">
      <WidgetRenderer :widget="widget" />
    </div>

    <p v-if="widget.status.last_run_at" class="border-t border-sky-100 px-4 py-1.5 text-[11px] text-slate-400">
      上次更新 {{ widget.status.last_run_at }}
      <span v-if="widget.status.last_status === 'error'" class="text-red-500">· 上次没取到数据</span>
      <span v-else-if="widget.status.last_status === 'paused'" class="text-amber-500">· 多次失败已暂停自动更新，点刷新可恢复</span>
      <span v-else-if="widget.status.next_run_at" class="text-slate-400">· 下次 {{ widget.status.next_run_at }}</span>
    </p>
    <p v-else class="border-t border-sky-100 px-4 py-1.5 text-[11px] text-slate-400">还没运行过 · 点右上角刷新</p>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BarChart3, Download, Eye, EyeOff, Pencil, RefreshCw, Trash2 } from 'lucide-vue-next'
import type { WidgetItem } from '../../../api/widget'
import WidgetRenderer from '../WidgetRenderer.vue'

const props = defineProps<{ widget: WidgetItem; running?: boolean; dragging?: boolean }>()
const emit = defineEmits<{
  (e: 'run' | 'detail' | 'export' | 'edit' | 'toggle' | 'delete' | 'dragstart' | 'dragend' | 'drop'): void
}>()

const ATTN_TEXT: Record<string, string> = { alert: '触发告警阈值', warn: '接近阈值', changed: '监控的网页有更新' }
const attentionLabel = computed(() => ATTN_TEXT[props.widget.attention || ''] || '')
const dotClass = computed(() => ({
  'bg-red-500': props.widget.attention === 'alert',
  'bg-amber-500': props.widget.attention === 'warn',
  'bg-sky-500': props.widget.attention === 'changed',
}))
const attentionRing = computed(() => ({
  'ring-1 ring-red-300': props.widget.attention === 'alert',
  'ring-1 ring-amber-300': props.widget.attention === 'warn',
  'ring-1 ring-sky-300': props.widget.attention === 'changed',
}))
</script>
