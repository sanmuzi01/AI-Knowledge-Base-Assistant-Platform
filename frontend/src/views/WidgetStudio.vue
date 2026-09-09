<template>
  <div class="flex h-screen flex-col bg-transparent">
    <header class="flex h-16 items-center justify-between border-b border-sky-200/70 bg-white/78 px-6 shadow-lg shadow-sky-900/8 backdrop-blur-xl">
      <div class="flex min-w-0 items-center gap-3">
        <button
          @click="router.push('/agents')"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="返回工作台"
        >
          <ArrowLeft :size="16" />
        </button>
        <div class="min-w-0">
          <h1 class="truncate text-base font-semibold text-slate-900">我的小窗口</h1>
          <p class="truncate text-xs text-slate-500">用一句话描述你想看的内容，AI 帮你做成小窗口放在这里</p>
        </div>
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
          @click="importOpen = true"
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
      <!-- 左：AI 创建组件 -->
      <section class="sci-panel h-fit rounded-lg p-5">
        <div class="flex items-center gap-2">
          <Sparkles :size="16" class="text-sky-500" />
          <h2 class="text-sm font-semibold text-slate-800">AI 创建组件</h2>
        </div>
        <p class="mt-1 text-xs text-slate-500">
          例如：每天早上看一次黄金价格走势折线图 / 用表格看美元汇率 / 监控某个网页有没有更新 /
          调用我自己的接口地址取数据 / 每天用 AI 把我的运行情况总结成一段话
        </p>

        <textarea
          v-model="prompt"
          rows="3"
          :disabled="designing"
          placeholder="说说你想要什么样的小窗口…"
          class="mt-3 w-full resize-none rounded border border-sky-200 bg-white/80 px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-400"
        ></textarea>

        <button
          @click="onDesign"
          :disabled="designing || !prompt.trim()"
          class="sci-primary mt-2 inline-flex w-full items-center justify-center gap-2 rounded px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Wand2 :size="15" />
          {{ designing ? '正在生成…' : '生成预览' }}
        </button>

        <!-- 追问 -->
        <div v-if="clarify" class="mt-3 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {{ clarify }}
        </div>

        <!-- 草稿预览 -->
        <div v-if="draftExplain" class="mt-3 rounded border border-sky-200 bg-sky-50/70 p-3">
          <p class="text-sm font-medium text-slate-800">{{ draft.name }}</p>
          <dl class="mt-2 space-y-1.5 text-xs text-slate-600">
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">数据从哪来</dt><dd>{{ draftExplain.data_from }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">系统会做</dt><dd>{{ draftExplain.system_does }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">怎么展示</dt><dd>{{ draftExplain.show_as }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">多久更新</dt><dd>{{ draftExplain.update_every }}</dd></div>
          </dl>

          <!-- 试运行结果 -->
          <div v-if="previewWidgetItem" class="mt-3 overflow-hidden rounded border border-sky-200 bg-white">
            <div class="border-b border-sky-100 bg-sky-50/60 px-2 py-1 text-[11px] text-slate-500">试运行效果</div>
            <div class="h-52"><WidgetRenderer :widget="previewWidgetItem" /></div>
          </div>
          <p v-else-if="previewError" class="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-600">
            试运行没成功：{{ previewError }}
          </p>

          <div class="mt-3 flex flex-wrap gap-2">
            <button
              @click="onPreview"
              :disabled="previewing"
              class="inline-flex items-center gap-1 rounded border border-sky-300 bg-white px-3 py-1.5 text-xs text-sky-700 hover:bg-sky-50 disabled:opacity-40"
            >
              <Play :size="13" />{{ previewing ? '运行中…' : '试运行' }}
            </button>
            <button
              @click="onCreate"
              :disabled="creating"
              class="sci-primary inline-flex flex-1 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
            >
              <Check :size="14" />{{ creating ? '创建中…' : '确认创建' }}
            </button>
            <button
              @click="resetDraft"
              class="rounded border border-sky-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50"
            >
              换个说法
            </button>
          </div>
        </div>
      </section>

      <!-- 右：小窗口网格 -->
      <section>
        <div v-if="loading" class="py-20 text-center text-sm text-slate-500">加载中…</div>
        <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          <div class="flex items-center justify-between gap-3">
            <span>{{ loadError }}</span>
            <button @click="reload" class="shrink-0 rounded border border-red-200 bg-white px-3 py-1.5 text-xs hover:bg-red-100">重试</button>
          </div>
        </div>
        <div v-else-if="!widgets.length" class="rounded-lg border border-dashed border-sky-200 bg-white/60 p-10 text-center text-sm text-slate-500">
          还没有小窗口。在左边描述一下你想看的内容，点"生成预览"试试。
        </div>
        <div v-else-if="!displayWidgets.length" class="rounded-lg border border-dashed border-emerald-200 bg-emerald-50/60 p-10 text-center text-sm text-emerald-700">
          目前没有需要关注的小窗口 🎉
        </div>

        <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <article
            v-for="w in displayWidgets"
            :key="w.id"
            draggable="true"
            @dragstart="dragId = w.id"
            @dragover.prevent
            @drop="onDrop(w)"
            @dragend="dragId = null"
            class="sci-panel flex flex-col rounded-lg transition-shadow"
            :class="[
              { 'opacity-60': !w.enabled, 'opacity-40': dragId === w.id },
              attentionRing(w),
            ]"
          >
            <div class="flex items-start justify-between gap-2 border-b border-sky-100 px-4 py-2.5">
              <div class="min-w-0">
                <p class="flex items-center gap-1.5 truncate text-sm font-medium text-slate-900">
                  <span
                    v-if="w.attention"
                    class="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                    :class="{ 'bg-red-500': w.attention === 'alert', 'bg-amber-500': w.attention === 'warn', 'bg-sky-500': w.attention === 'changed' }"
                    :title="attentionLabel(w.attention)"
                  ></span>
                  {{ w.name }}
                </p>
                <p class="truncate text-[11px] text-slate-400">
                  {{ w.friendly.data_from }} · {{ w.friendly.update_every }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <button
                  @click="onRun(w)"
                  :disabled="runningId === w.id"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600 disabled:opacity-40"
                  title="刷新"
                >
                  <RefreshCw :size="13" :class="{ 'animate-spin': runningId === w.id }" />
                </button>
                <button
                  @click="openDetail(w)"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600"
                  title="详情与历史"
                >
                  <BarChart3 :size="13" />
                </button>
                <button
                  @click="onExport(w)"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600"
                  title="导出配置"
                >
                  <Download :size="13" />
                </button>
                <button
                  @click="openEdit(w)"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600"
                  title="编辑"
                >
                  <Pencil :size="13" />
                </button>
                <button
                  @click="onToggle(w)"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-sky-50 hover:text-sky-600"
                  :title="w.enabled ? '隐藏' : '显示'"
                >
                  <EyeOff v-if="w.enabled" :size="13" />
                  <Eye v-else :size="13" />
                </button>
                <button
                  @click="onDelete(w)"
                  class="inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                  title="删除"
                >
                  <Trash2 :size="13" />
                </button>
              </div>
            </div>

            <div class="min-h-[220px] flex-1">
              <WidgetRenderer :widget="w" />
            </div>

            <p v-if="w.status.last_run_at" class="border-t border-sky-100 px-4 py-1.5 text-[11px] text-slate-400">
              上次更新 {{ w.status.last_run_at }}
              <span v-if="w.status.last_status === 'error'" class="text-red-500">· 上次没取到数据</span>
              <span v-else-if="w.status.last_status === 'paused'" class="text-amber-500">· 多次失败已暂停自动更新，点刷新可恢复</span>
              <span v-else-if="w.status.next_run_at" class="text-slate-400">· 下次 {{ w.status.next_run_at }}</span>
            </p>
            <p v-else class="border-t border-sky-100 px-4 py-1.5 text-[11px] text-slate-400">还没运行过 · 点右上角刷新</p>
          </article>
        </div>
      </section>
    </main>

    <!-- 编辑弹窗 -->
    <div v-if="editTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="editTarget = null">
      <div class="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
        <h3 class="text-sm font-semibold text-slate-900">编辑小窗口</h3>
        <label class="mt-3 block text-xs text-slate-500">名称</label>
        <input
          v-model="editName"
          class="mt-1 w-full rounded border border-sky-200 px-3 py-2 text-sm outline-none focus:border-sky-400"
        />
        <label class="mt-3 block text-xs text-slate-500">备注（可选）</label>
        <input
          v-model="editDesc"
          class="mt-1 w-full rounded border border-sky-200 px-3 py-2 text-sm outline-none focus:border-sky-400"
        />
        <div class="mt-4 flex justify-end gap-2">
          <button @click="editTarget = null" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">取消</button>
          <button
            @click="onSaveEdit"
            :disabled="savingEdit"
            class="sci-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          >
            {{ savingEdit ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 详情 / 历史弹窗 -->
    <div v-if="detailTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8" @click.self="detailTarget = null">
      <div class="flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div class="flex items-center justify-between border-b border-sky-100 px-5 py-3">
          <h3 class="text-sm font-semibold text-slate-900">{{ detailTarget.name }}</h3>
          <button @click="detailTarget = null" class="text-slate-400 hover:text-slate-600"><X :size="16" /></button>
        </div>

        <div class="min-h-0 flex-1 overflow-auto p-5">
          <dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-slate-600">
            <div class="flex gap-2"><dt class="text-slate-400">数据从哪来</dt><dd>{{ detailTarget.friendly.data_from }}</dd></div>
            <div class="flex gap-2"><dt class="text-slate-400">系统会做</dt><dd>{{ detailTarget.friendly.system_does }}</dd></div>
            <div class="flex gap-2"><dt class="text-slate-400">怎么展示</dt><dd>{{ detailTarget.friendly.show_as }}</dd></div>
            <div class="flex gap-2"><dt class="text-slate-400">多久更新</dt><dd>{{ detailTarget.friendly.update_every }}</dd></div>
            <div class="flex gap-2"><dt class="text-slate-400">上次运行</dt><dd>{{ detailTarget.status.last_run_at || '—' }}（{{ statusLabel(detailTarget.status.last_status) }}）</dd></div>
            <div class="flex gap-2"><dt class="text-slate-400">下次自动</dt><dd>{{ detailTarget.status.next_run_at || '手动刷新' }}</dd></div>
          </dl>

          <div class="mt-4 overflow-hidden rounded border border-sky-100">
            <div class="border-b border-sky-100 bg-sky-50/60 px-3 py-1.5 text-[11px] text-slate-500">当前内容</div>
            <div class="h-56"><WidgetRenderer :widget="detailTarget" /></div>
          </div>

          <div class="mt-4">
            <p class="mb-1.5 text-xs font-medium text-slate-600">运行历史（近 {{ detailSeries.length }} 次）</p>
            <div v-if="detailLoading" class="py-6 text-center text-xs text-slate-400">加载中…</div>
            <div v-else-if="!detailSeries.length" class="py-6 text-center text-xs text-slate-400">还没有历史记录</div>
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
                  <tr v-for="(p, i) in detailSeriesDesc" :key="i" class="border-t border-slate-100">
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
          <button @click="onRun(detailTarget); " class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">立即刷新</button>
          <button @click="detailTarget = null" class="sci-primary rounded px-3 py-1.5 text-xs font-medium text-white">关闭</button>
        </div>
      </div>
    </div>

    <!-- 导出弹窗 -->
    <div v-if="exportJson" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="exportJson = ''">
      <div class="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
        <h3 class="text-sm font-semibold text-slate-900">导出小窗口配置</h3>
        <p class="mt-1 text-xs text-slate-500">复制下面的内容，发给别人 → 对方用「导入」粘贴即可得到同样的小窗口。</p>
        <textarea
          :value="exportJson"
          readonly
          rows="10"
          class="mt-3 w-full resize-none rounded border border-sky-200 bg-slate-50 p-2 font-mono text-[11px] text-slate-700 outline-none"
        ></textarea>
        <div class="mt-3 flex justify-end gap-2">
          <button @click="exportJson = ''" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">关闭</button>
          <button @click="copyExport" class="sci-primary inline-flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-white">
            <Copy :size="13" />{{ copied ? '已复制' : '复制' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 导入弹窗 -->
    <div v-if="importOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="importOpen = false">
      <div class="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
        <h3 class="text-sm font-semibold text-slate-900">导入小窗口</h3>
        <p class="mt-1 text-xs text-slate-500">把别人导出的 JSON 粘贴到这里。</p>
        <textarea
          v-model="importText"
          rows="10"
          placeholder='{"export_version": 1, "spec": { … }}'
          class="mt-3 w-full resize-none rounded border border-sky-200 bg-white p-2 font-mono text-[11px] text-slate-700 outline-none focus:border-sky-400"
        ></textarea>
        <p v-if="importError" class="mt-2 text-xs text-red-600">{{ importError }}</p>
        <div class="mt-3 flex justify-end gap-2">
          <button @click="importOpen = false" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">取消</button>
          <button @click="onImport" :disabled="importing || !importText.trim()" class="sci-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
            {{ importing ? '导入中…' : '导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, BarChart3, Bell, Check, Copy, Download, Eye, EyeOff, Pencil, Play,
  RefreshCcw, RefreshCw, Sparkles, Trash2, Upload, Wand2, X,
} from 'lucide-vue-next'
import {
  createWidget,
  deleteWidget,
  designWidget,
  exportWidget,
  getWidgetData,
  importWidget,
  listWidgets,
  previewWidget,
  runWidget,
  updateWidget,
  type WidgetFriendly,
  type WidgetItem,
  type WidgetSeriesPoint,
} from '../api/widget'
import { getErrorMessage } from '../utils/request'
import { toastError, toastSuccess } from '../utils/toast'
import WidgetRenderer from '../components/widgets/WidgetRenderer.vue'

const router = useRouter()

const widgets = ref<WidgetItem[]>([])
const loading = ref(true)
const loadError = ref('')

const prompt = ref('')
const designing = ref(false)
const creating = ref(false)
const clarify = ref('')
const draft = ref<any>(null)
const draftExplain = ref<WidgetFriendly | null>(null)

const previewing = ref(false)
const previewError = ref('')
const previewWidgetItem = ref<WidgetItem | null>(null)

const runningId = ref<number | null>(null)

const editTarget = ref<WidgetItem | null>(null)
const editName = ref('')
const editDesc = ref('')
const savingEdit = ref(false)

const detailTarget = ref<WidgetItem | null>(null)
const detailSeries = ref<WidgetSeriesPoint[]>([])
const detailLoading = ref(false)
const detailSeriesDesc = computed(() => [...detailSeries.value].reverse())

const onlyAttention = ref(false)
const dragId = ref<number | null>(null)

const exportJson = ref('')
const copied = ref(false)
const importOpen = ref(false)
const importText = ref('')
const importError = ref('')
const importing = ref(false)

const ATTN_RANK: Record<string, number> = { alert: 3, warn: 2, changed: 1 }
const attentionCount = computed(() => widgets.value.filter((w) => w.attention).length)
const displayWidgets = computed(() => {
  const list = onlyAttention.value ? widgets.value.filter((w) => w.attention) : widgets.value.slice()
  return list.sort(
    (a, b) => (ATTN_RANK[b.attention || ''] || 0) - (ATTN_RANK[a.attention || ''] || 0) || a.sort_order - b.sort_order,
  )
})

function statusLabel(s: string | null) {
  return { ok: '成功', error: '失败', paused: '已暂停' }[s || ''] || '未运行'
}
function attentionLabel(a: string | null) {
  return { alert: '触发告警阈值', warn: '接近阈值', changed: '监控的网页有更新' }[a || ''] || ''
}
function attentionRing(w: WidgetItem) {
  return {
    'ring-1 ring-red-300': w.attention === 'alert',
    'ring-1 ring-amber-300': w.attention === 'warn',
    'ring-1 ring-sky-300': w.attention === 'changed',
  }
}

async function onExport(w: WidgetItem) {
  try {
    const data = await exportWidget(w.id)
    exportJson.value = JSON.stringify(data, null, 2)
    copied.value = false
  } catch (e: any) {
    toastError(getErrorMessage(e, '导出失败'))
  }
}
async function copyExport() {
  try {
    await navigator.clipboard.writeText(exportJson.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    toastError('复制失败，请手动选择文本复制')
  }
}
async function onImport() {
  importError.value = ''
  let parsed: any
  try {
    parsed = JSON.parse(importText.value)
  } catch {
    importError.value = '不是有效的 JSON'
    return
  }
  importing.value = true
  try {
    await importWidget(parsed)
    toastSuccess('已导入')
    importOpen.value = false
    importText.value = ''
    await reload()
  } catch (e: any) {
    importError.value = getErrorMessage(e, '导入失败')
  } finally {
    importing.value = false
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
  // 重排 sort_order 并把有变化的推给后端
  const changed: { id: number; sort_order: number }[] = []
  ordered.forEach((w, i) => {
    if (w.sort_order !== i) {
      w.sort_order = i
      changed.push({ id: w.id, sort_order: i })
    }
  })
  try {
    await Promise.all(changed.map((c) => updateWidget(c.id, { sort_order: c.sort_order })))
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '排序失败'))
    await reload()
  }
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listWidgets()
    widgets.value = res.items
    if (detailTarget.value) {
      const fresh = res.items.find((x) => x.id === detailTarget.value!.id)
      if (fresh) detailTarget.value = fresh
    }
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function resetDraft() {
  draft.value = null
  draftExplain.value = null
  previewWidgetItem.value = null
  previewError.value = ''
}

async function onDesign() {
  if (!prompt.value.trim()) return
  designing.value = true
  clarify.value = ''
  resetDraft()
  try {
    const res = await designWidget(prompt.value.trim())
    if (res.needs_clarification) {
      clarify.value = res.message || '需要再补充一点信息'
    } else {
      draft.value = res.draft
      draftExplain.value = res.explain || null
    }
  } catch (e: any) {
    toastError(getErrorMessage(e, '生成失败'))
  } finally {
    designing.value = false
  }
}

async function onPreview() {
  if (!draft.value) return
  previewing.value = true
  previewError.value = ''
  previewWidgetItem.value = null
  try {
    const res = await previewWidget(draft.value)
    if (!res.ok) {
      previewError.value = res.message || '没取到数据'
      return
    }
    previewWidgetItem.value = {
      id: -1,
      name: draft.value.name,
      type: draft.value.type,
      type_label: '',
      description: '',
      enabled: true,
      sort_order: 0,
      spec_version: 1,
      view_kind: res.view_kind,
      view: res.view,
      actions: [],
      friendly: res.explain as WidgetFriendly,
      config: {},
      attention: null,
      status: { last_run_at: null, last_status: null, fail_count: 0, next_run_at: null },
      latest: { ok: true, label: res.label ?? null, value: res.value ?? null, error: null, payload: res.data, recorded_at: null },
    }
  } catch (e: any) {
    previewError.value = getErrorMessage(e, '试运行失败')
  } finally {
    previewing.value = false
  }
}

async function onCreate() {
  if (!draft.value) return
  creating.value = true
  try {
    const created = await createWidget(draft.value)
    toastSuccess('已添加到你的工作台')
    resetDraft()
    prompt.value = ''
    try {
      await runWidget(created.id)
    } catch {
      /* 首次运行失败不阻塞，卡片里会有提示 */
    }
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '创建失败'))
  } finally {
    creating.value = false
  }
}

async function onRun(w: WidgetItem) {
  runningId.value = w.id
  try {
    const res = await runWidget(w.id)
    if (!res.ok) toastError(res.message || '这次没取到数据')
    await reload()
    if (detailTarget.value && detailTarget.value.id === w.id) await loadDetailSeries(w.id)
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

function openEdit(w: WidgetItem) {
  editTarget.value = w
  editName.value = w.name
  editDesc.value = w.description
}

async function onSaveEdit() {
  if (!editTarget.value) return
  savingEdit.value = true
  try {
    await updateWidget(editTarget.value.id, { name: editName.value.trim(), description: editDesc.value.trim() })
    editTarget.value = null
    await reload()
  } catch (e: any) {
    toastError(getErrorMessage(e, '保存失败'))
  } finally {
    savingEdit.value = false
  }
}

async function loadDetailSeries(id: number) {
  detailLoading.value = true
  try {
    const res = await getWidgetData(id, true)
    detailSeries.value = res.series || []
  } catch {
    detailSeries.value = []
  } finally {
    detailLoading.value = false
  }
}

async function openDetail(w: WidgetItem) {
  detailTarget.value = w
  detailSeries.value = []
  await loadDetailSeries(w.id)
}

onMounted(reload)
</script>
