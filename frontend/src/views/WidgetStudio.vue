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
      <button
        @click="reload"
        class="inline-flex h-8 w-8 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
        title="刷新"
      >
        <RefreshCcw :size="15" />
      </button>
    </header>

    <main class="grid min-h-0 flex-1 grid-cols-1 gap-5 overflow-y-auto p-5 lg:grid-cols-[380px_minmax(0,1fr)]">
      <!-- 左：AI 创建组件 -->
      <section class="sci-panel h-fit rounded-lg p-5">
        <div class="flex items-center gap-2">
          <Sparkles :size="16" class="text-sky-500" />
          <h2 class="text-sm font-semibold text-slate-800">AI 创建组件</h2>
        </div>
        <p class="mt-1 text-xs text-slate-500">
          例如：每天早上看一次黄金价格走势折线图 / 用表格看美元汇率 / 一张卡片显示我这周的 AI 使用情况
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

        <!-- 草稿预览：只给用户看四句话 -->
        <div v-if="draftExplain" class="mt-3 rounded border border-sky-200 bg-sky-50/70 p-3">
          <p class="text-sm font-medium text-slate-800">{{ draft.name }}</p>
          <dl class="mt-2 space-y-1.5 text-xs text-slate-600">
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">数据从哪来</dt><dd>{{ draftExplain.data_from }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">系统会做</dt><dd>{{ draftExplain.system_does }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">怎么展示</dt><dd>{{ draftExplain.show_as }}</dd></div>
            <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">多久更新</dt><dd>{{ draftExplain.update_every }}</dd></div>
          </dl>
          <div class="mt-3 flex gap-2">
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
          还没有小窗口。在左边描述一下你想看的内容，点“生成预览”试试。
        </div>

        <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <article
            v-for="w in widgets"
            :key="w.id"
            class="sci-panel flex flex-col rounded-lg"
            :class="{ 'opacity-60': !w.enabled }"
          >
            <div class="flex items-start justify-between gap-2 border-b border-sky-100 px-4 py-2.5">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-900">{{ w.name }}</p>
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
            </p>
            <p v-else class="border-t border-sky-100 px-4 py-1.5 text-[11px] text-slate-400">还没运行过 · 点右上角刷新</p>
          </article>
        </div>
      </section>
    </main>

    <!-- 编辑弹窗（P1：改名 + 说明） -->
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Check, Eye, EyeOff, Pencil, RefreshCcw, RefreshCw, Sparkles, Trash2, Wand2 } from 'lucide-vue-next'
import {
  createWidget,
  deleteWidget,
  designWidget,
  listWidgets,
  runWidget,
  updateWidget,
  type WidgetFriendly,
  type WidgetItem,
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

const runningId = ref<number | null>(null)

const editTarget = ref<WidgetItem | null>(null)
const editName = ref('')
const editDesc = ref('')
const savingEdit = ref(false)

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listWidgets()
    widgets.value = res.items
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function resetDraft() {
  draft.value = null
  draftExplain.value = null
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

async function onCreate() {
  if (!draft.value) return
  creating.value = true
  try {
    const created = await createWidget(draft.value)
    toastSuccess('已添加到你的工作台')
    resetDraft()
    prompt.value = ''
    // 新组件立刻运行一次，让它有内容
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

onMounted(reload)
</script>
