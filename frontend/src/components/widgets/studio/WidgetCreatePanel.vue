<template>
  <section class="sci-panel h-fit rounded-lg p-5">
    <div class="flex items-center gap-2">
      <LayoutGrid :size="16" class="text-sky-500" />
      <h2 class="text-sm font-semibold text-slate-800">添加小窗口</h2>
    </div>
    <p class="mt-1 text-xs text-slate-500">选一个模板，填几个字段就能建。</p>

    <div class="mt-3">
      <WidgetTemplateGallery @created="emit('created')" />
    </div>

    <details class="mt-4 rounded border border-slate-200 bg-slate-50/70">
      <summary class="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-600">
        高级：用一句话描述（实验性）
      </summary>
      <div class="border-t border-slate-200 p-3">
    <p class="text-[11px] leading-5 text-slate-400">
      描述数据来源、展示形式、更新频率。模板覆盖不到的需求可以试试；识别不准时会追问。
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

    <div v-if="clarify" class="mt-3 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
      {{ clarify }}
    </div>

    <div v-if="draftExplain" class="mt-3 rounded border border-sky-200 bg-sky-50/70 p-3">
      <p class="text-sm font-medium text-slate-800">{{ draft.name }}</p>
      <dl class="mt-2 space-y-1.5 text-xs text-slate-600">
        <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">数据从哪来</dt><dd>{{ draftExplain.data_from }}</dd></div>
        <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">系统会做</dt><dd>{{ draftExplain.system_does }}</dd></div>
        <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">怎么展示</dt><dd>{{ draftExplain.show_as }}</dd></div>
        <div class="flex gap-2"><dt class="w-20 shrink-0 text-slate-400">多久更新</dt><dd>{{ draftExplain.update_every }}</dd></div>
      </dl>

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
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Check, LayoutGrid, Play, Wand2 } from 'lucide-vue-next'
import { createWidget, designWidget, previewWidget, runWidget, type WidgetFriendly, type WidgetItem } from '../../../api/widget'
import { getErrorMessage } from '../../../utils/request'
import { toastError, toastSuccess } from '../../../utils/toast'
import WidgetRenderer from '../WidgetRenderer.vue'
import WidgetTemplateGallery from './WidgetTemplateGallery.vue'

const emit = defineEmits<{ (e: 'created'): void }>()

const prompt = ref('')
const designing = ref(false)
const creating = ref(false)
const clarify = ref('')
const draft = ref<any>(null)
const draftExplain = ref<WidgetFriendly | null>(null)

const previewing = ref(false)
const previewError = ref('')
const previewWidgetItem = ref<WidgetItem | null>(null)

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
    emit('created')
  } catch (e: any) {
    toastError(getErrorMessage(e, '创建失败'))
  } finally {
    creating.value = false
  }
}
</script>
