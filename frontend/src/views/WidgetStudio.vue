<template>
  <div class="flex h-screen flex-col bg-transparent">
    <header class="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-sky-200/70 bg-white/78 px-6 py-2 shadow-lg shadow-sky-900/8 backdrop-blur-xl">
      <div class="flex min-w-0 flex-col gap-1.5">
        <SectionTabs :tabs="[
          { label: '我的小窗口', path: '/widgets' },
          { label: '网页监控', path: '/web-monitor' },
        ]" />
        <p class="truncate text-xs text-slate-500">从模板挑一个，填几个字段就能把想盯的东西做成小窗口</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="onlyAttention = !onlyAttention"
          class="inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-xs"
          :class="onlyAttention ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50'"
          title="只看需要关注的小窗口"
        >
          <Bell :size="13" />
          需关注<span v-if="attentionCount">（{{ attentionCount }}）</span>
        </button>
        <button
          @click="transferMode = 'import'"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="导入小窗口"
        >
          <Upload :size="15" />
        </button>
        <button
          @click="reload"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="刷新"
        >
          <RefreshCcw :size="15" />
        </button>
      </div>
    </header>

    <main class="grid min-h-0 flex-1 grid-cols-1 gap-5 overflow-y-auto p-5 lg:grid-cols-[380px_minmax(0,1fr)]">
      <WidgetCreatePanel @created="onCreated" />

      <section>
        <div v-if="loading" class="py-20 text-center text-sm text-slate-500">加载中…</div>
        <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          <div class="flex items-center justify-between gap-3">
            <span>{{ loadError }}</span>
            <button @click="reload" class="shrink-0 rounded border border-red-200 bg-white px-3 py-1.5 text-xs hover:bg-red-100">重试</button>
          </div>
        </div>
        <div v-else-if="!widgets.length" class="rounded-lg border border-dashed border-sky-200 bg-white/60 p-10 text-center text-sm text-slate-500">
          还没有小窗口。左边选一个模板，填几个字段就能建。
        </div>
        <div v-else-if="!displayWidgets.length" class="rounded-lg border border-dashed border-emerald-200 bg-emerald-50/60 p-10 text-center text-sm text-emerald-700">
          目前没有需要关注的小窗口 🎉
        </div>

        <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <WidgetCard
            v-for="w in displayWidgets"
            :key="w.id"
            :widget="w"
            :running="runningId === w.id"
            :dragging="dragId === w.id"
            @run="onRun(w)"
            @detail="detailTarget = w"
            @export="onExport(w)"
            @edit="editTarget = w"
            @toggle="onToggle(w)"
            @delete="onDelete(w)"
            @dragstart="dragId = w.id"
            @dragend="dragId = null"
            @drop="onDrop(w)"
          />
        </div>
      </section>
    </main>

    <WidgetEditDialog
      v-if="editTarget"
      :widget="editTarget"
      @close="editTarget = null"
      @saved="editTarget = null; reload()"
    />

    <WidgetDetailDialog
      v-if="detailTarget"
      :widget="detailTarget"
      :reload-key="detailReloadKey"
      @close="detailTarget = null"
      @run="onRun(detailTarget)"
    />

    <WidgetTransferDialog
      :mode="transferMode"
      :json="exportJson"
      @close="transferMode = null; exportJson = ''"
      @imported="transferMode = null; reload()"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Bell, RefreshCcw, Upload } from 'lucide-vue-next'
import SectionTabs from '../components/SectionTabs.vue'
import {
  deleteWidget,
  exportWidget,
  listWidgets,
  runWidget,
  updateWidget,
  type WidgetItem,
} from '../api/widget'
import { getErrorMessage } from '../utils/request'
import { toastError, toastSuccess } from '../utils/toast'
import WidgetCreatePanel from '../components/widgets/studio/WidgetCreatePanel.vue'
import WidgetCard from '../components/widgets/studio/WidgetCard.vue'
import WidgetEditDialog from '../components/widgets/studio/WidgetEditDialog.vue'
import WidgetDetailDialog from '../components/widgets/studio/WidgetDetailDialog.vue'
import WidgetTransferDialog from '../components/widgets/studio/WidgetTransferDialog.vue'


const widgets = ref<WidgetItem[]>([])
const loading = ref(true)
const loadError = ref('')
const runningId = ref<number | null>(null)

const editTarget = ref<WidgetItem | null>(null)
const detailTarget = ref<WidgetItem | null>(null)
const detailReloadKey = ref(0)

const onlyAttention = ref(false)
const dragId = ref<number | null>(null)

const transferMode = ref<'import' | 'export' | null>(null)
const exportJson = ref('')

const ATTN_RANK: Record<string, number> = { alert: 3, warn: 2, changed: 1 }
const attentionCount = computed(() => widgets.value.filter((w) => w.attention).length)
const displayWidgets = computed(() => {
  const list = onlyAttention.value ? widgets.value.filter((w) => w.attention) : widgets.value.slice()
  return list.sort(
    (a, b) => (ATTN_RANK[b.attention || ''] || 0) - (ATTN_RANK[a.attention || ''] || 0) || a.sort_order - b.sort_order,
  )
})

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listWidgets()
    widgets.value = res.items
    if (detailTarget.value) {
      const fresh = res.items.find((x) => x.id === detailTarget.value!.id)
      detailTarget.value = fresh ?? null
    }
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function onCreated() {
  reload()
}

async function onRun(w: WidgetItem | null) {
  if (!w) return
  runningId.value = w.id
  try {
    const res = await runWidget(w.id)
    if (!res.ok) toastError(res.message || '这次没取到数据')
    await reload()
    if (detailTarget.value?.id === w.id) detailReloadKey.value++
  } catch (e: any) {
    toastError(getErrorMessage(e, '刷新失败'))
  } finally {
    runningId.value = null
  }
}

async function onToggle(w: WidgetItem) {
  try {
    await updateWidget(w.id, { enabled: !w.enabled })
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '操作失败'))
  }
}

async function onDelete(w: WidgetItem) {
  if (!window.confirm(`确定删除「${w.name}」吗？`)) return
  try {
    await deleteWidget(w.id)
    toastSuccess('已删除')
    if (detailTarget.value?.id === w.id) detailTarget.value = null
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '删除失败'))
  }
}

async function onExport(w: WidgetItem) {
  try {
    const data = await exportWidget(w.id)
    exportJson.value = JSON.stringify(data, null, 2)
    transferMode.value = 'export'
  } catch (e: any) {
    toastError(getErrorMessage(e, '导出失败'))
  }
}

async function onDrop(target: WidgetItem) {
  const from = dragId.value
  dragId.value = null
  if (from == null || from === target.id) return
  const ordered = displayWidgets.value.slice()
  const fromIdx = ordered.findIndex((w) => w.id === from)
  const toIdx = ordered.findIndex((w) => w.id === target.id)
  if (fromIdx < 0 || toIdx < 0) return
  const [moved] = ordered.splice(fromIdx, 1)
  ordered.splice(toIdx, 0, moved)
  const changed: { id: number; sort_order: number }[] = []
  ordered.forEach((w, i) => {
    if (w.sort_order !== i) {
      w.sort_order = i
      changed.push({ id: w.id, sort_order: i })
    }
  })
  try {
    await Promise.all(changed.map((c) => updateWidget(c.id, { sort_order: c.sort_order })))
  } catch (e: any) {
    toastError(getErrorMessage(e, '排序失败'))
  } finally {
    await reload()
  }
}

onMounted(reload)
</script>
