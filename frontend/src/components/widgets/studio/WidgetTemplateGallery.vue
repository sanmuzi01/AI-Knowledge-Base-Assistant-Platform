<template>
  <div>
    <!-- 模板选择 -->
    <div v-if="!active">
      <p v-if="loadError" class="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-600">{{ loadError }}</p>
      <div v-else-if="loading" class="py-8 text-center text-xs text-slate-400">加载模板…</div>
      <div v-else class="grid gap-2">
        <button
          v-for="t in templates"
          :key="t.key"
          @click="pick(t)"
          class="rounded-lg border border-sky-200 bg-white/80 p-3 text-left transition hover:border-sky-400 hover:bg-sky-50/60"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-slate-800">{{ t.name }}</span>
            <span v-if="t.experimental" class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">实验性</span>
          </div>
          <p class="mt-0.5 text-xs leading-5 text-slate-500">{{ t.description }}</p>
        </button>
      </div>
    </div>

    <!-- 选中模板后的表单 -->
    <div v-else>
      <button class="mb-2 text-xs text-slate-500 hover:text-slate-800" @click="reset">← 换个模板</button>
      <div class="rounded-lg border border-sky-200 bg-sky-50/60 p-3">
        <p class="text-sm font-medium text-slate-800">{{ active.name }}</p>
        <p class="mt-0.5 text-xs text-slate-500">{{ active.description }}</p>

        <div class="mt-3 space-y-2.5">
          <div v-for="f in visibleFields" :key="f.name">
            <label class="mb-1 block text-xs font-medium text-slate-600">
              {{ f.label }}<span v-if="f.required" class="text-red-400">*</span>
            </label>

            <select
              v-if="f.type === 'select'"
              v-model="form[f.name]"
              class="h-9 w-full rounded border border-slate-300 bg-white px-2 text-sm outline-none focus:border-sky-400"
            >
              <option v-for="o in f.options" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>

            <select
              v-else-if="f.type === 'agent' || f.type === 'space'"
              v-model="form[f.name]"
              class="h-9 w-full rounded border border-slate-300 bg-white px-2 text-sm outline-none focus:border-sky-400"
            >
              <option value="">{{ f.type === 'agent' ? '选择助手' : '选择知识库空间' }}</option>
              <option v-for="o in (f.type === 'agent' ? agents : spaces)" :key="o.value" :value="o.value">
                {{ o.label }}
              </option>
            </select>

            <textarea
              v-else-if="f.type === 'textarea'"
              v-model="form[f.name]"
              rows="2"
              :placeholder="f.placeholder"
              class="w-full resize-none rounded border border-slate-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-sky-400"
            ></textarea>

            <input
              v-else
              v-model="form[f.name]"
              :type="f.type === 'number' ? 'number' : f.type === 'time' ? 'time' : 'text'"
              :min="f.min"
              :max="f.max"
              :placeholder="f.placeholder"
              class="h-9 w-full rounded border border-slate-300 bg-white px-2 text-sm outline-none focus:border-sky-400"
            />

            <p v-if="f.help" class="mt-0.5 text-[11px] text-slate-400">{{ f.help }}</p>
          </div>
        </div>

        <p v-if="error" class="mt-3 rounded border border-red-200 bg-red-50 px-2 py-1.5 text-xs text-red-600">{{ error }}</p>

        <div v-if="draftExplain" class="mt-3 rounded border border-sky-200 bg-white p-2.5">
          <dl class="space-y-1 text-xs text-slate-600">
            <div class="flex gap-2"><dt class="w-16 shrink-0 text-slate-400">数据</dt><dd>{{ draftExplain.data_from }}</dd></div>
            <div class="flex gap-2"><dt class="w-16 shrink-0 text-slate-400">处理</dt><dd>{{ draftExplain.system_does }}</dd></div>
            <div class="flex gap-2"><dt class="w-16 shrink-0 text-slate-400">展示</dt><dd>{{ draftExplain.show_as }}</dd></div>
            <div class="flex gap-2"><dt class="w-16 shrink-0 text-slate-400">更新</dt><dd>{{ draftExplain.update_every }}</dd></div>
          </dl>
          <div v-if="previewItem" class="mt-2 overflow-hidden rounded border border-sky-100">
            <div class="bg-sky-50/60 px-2 py-1 text-[11px] text-slate-500">试运行效果</div>
            <div class="h-44"><WidgetRenderer :widget="previewItem" /></div>
          </div>
          <p v-else-if="previewError" class="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-700">
            试运行没成功：{{ previewError }}
          </p>
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            @click="onBuildPreview"
            :disabled="!!busy"
            class="inline-flex items-center gap-1 rounded border border-sky-300 bg-white px-3 py-1.5 text-xs text-sky-700 hover:bg-sky-50 disabled:opacity-40"
          >
            <Play :size="13" />{{ busy === 'preview' ? '运行中…' : draftExplain ? '重新试运行' : '生成并试运行' }}
          </button>
          <button
            @click="onCreate"
            :disabled="!!busy || !draft"
            class="sci-primary inline-flex flex-1 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
          >
            <Check :size="14" />{{ busy === 'create' ? '创建中…' : '确认创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Check, Play } from 'lucide-vue-next'
import {
  buildWidgetFromTemplate,
  createWidget,
  listWidgetTemplates,
  previewWidget,
  runWidget,
  type TemplateField,
  type WidgetFriendly,
  type WidgetItem,
  type WidgetTemplate,
} from '../../../api/widget'
import { getErrorMessage } from '../../../utils/request'
import { toastError, toastSuccess } from '../../../utils/toast'
import WidgetRenderer from '../WidgetRenderer.vue'

const emit = defineEmits<{ (e: 'created'): void }>()

const loading = ref(true)
const loadError = ref('')
const templates = ref<WidgetTemplate[]>([])
const agents = ref<{ value: number; label: string }[]>([])
const spaces = ref<{ value: number; label: string }[]>([])

const active = ref<WidgetTemplate | null>(null)
const form = reactive<Record<string, any>>({})
const busy = ref<'' | 'preview' | 'create'>('')
const error = ref('')
const draft = ref<any>(null)
const draftExplain = ref<WidgetFriendly | null>(null)
const previewItem = ref<WidgetItem | null>(null)
const previewError = ref('')

const visibleFields = computed<TemplateField[]>(() => {
  if (!active.value) return []
  return active.value.fields.filter((f) => {
    if (!f.show_if) return true
    const cur = form[f.show_if.field]
    if (f.show_if.eq !== undefined) return cur === f.show_if.eq
    if (f.show_if.in) return f.show_if.in.includes(cur)
    return true
  })
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listWidgetTemplates()
    templates.value = res.templates
    agents.value = res.options.agents
    spaces.value = res.options.spaces
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '模板加载失败')
  } finally {
    loading.value = false
  }
}

function pick(t: WidgetTemplate) {
  active.value = t
  clearDraft()
  Object.keys(form).forEach((k) => delete form[k])
  t.fields.forEach((f) => {
    form[f.name] = f.default ?? (f.type === 'number' ? '' : '')
  })
}

function reset() {
  active.value = null
  clearDraft()
}

function clearDraft() {
  draft.value = null
  draftExplain.value = null
  previewItem.value = null
  previewError.value = ''
  error.value = ''
}

function currentParams() {
  const p: Record<string, any> = {}
  visibleFields.value.forEach((f) => {
    const v = form[f.name]
    if (v !== '' && v !== null && v !== undefined) p[f.name] = v
  })
  return p
}

async function onBuildPreview() {
  if (!active.value || busy.value) return
  busy.value = 'preview'
  error.value = ''
  previewItem.value = null
  previewError.value = ''
  try {
    const built = await buildWidgetFromTemplate(active.value.key, currentParams())
    draft.value = built.draft
    draftExplain.value = built.explain
    const res = await previewWidget(built.draft)
    if (!res.ok) {
      previewError.value = res.message || '没取到数据'
    } else {
      previewItem.value = {
        id: -1, name: built.draft.name, type: built.draft.type, type_label: '',
        description: '', enabled: true, sort_order: 0, spec_version: 1,
        view_kind: res.view_kind, view: res.view, actions: [],
        friendly: built.explain, config: {}, attention: null,
        status: { last_run_at: null, last_status: null, fail_count: 0, next_run_at: null },
        latest: { ok: true, label: res.label ?? null, value: res.value ?? null, error: null, payload: res.data, recorded_at: null },
      }
    }
  } catch (e: any) {
    error.value = getErrorMessage(e, '生成失败，检查一下填的内容')
  } finally {
    busy.value = ''
  }
}

async function onCreate() {
  if (!draft.value || busy.value) return
  busy.value = 'create'
  try {
    const created = await createWidget(draft.value)
    toastSuccess('已添加到工作台')
    runWidget(created.id).catch(() => {})
    reset()
    emit('created')
  } catch (e: any) {
    toastError(getErrorMessage(e, '创建失败'))
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>
