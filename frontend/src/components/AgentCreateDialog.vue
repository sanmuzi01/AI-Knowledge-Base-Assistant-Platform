<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="$emit('close')">
    <div class="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-white shadow-xl">
      <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
        <h2 class="text-base font-semibold text-slate-900">{{ agent ? '编辑 Agent' : '新建 Agent' }}</h2>
        <button
          @click="$emit('close')"
          class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          title="关闭"
        >
          <X :size="16" />
        </button>
      </header>

      <main class="flex-1 overflow-y-auto px-5 py-4">
        <section v-if="!agent" class="mb-4 rounded-lg border border-slate-200 p-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <Sparkles :size="16" class="text-slate-500" />
              <h3 class="text-sm font-semibold text-slate-800">创建方式</h3>
            </div>
            <button
              @click="startBlank"
              type="button"
              :class="[
                'rounded border px-2 py-1 text-xs',
                selectedTemplateId === '' ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50',
              ]"
            >
              空白自定义
            </button>
          </div>
          <div v-if="templateLoading" class="rounded border border-slate-100 bg-slate-50 px-3 py-4 text-center text-sm text-slate-500">
            模板加载中...
          </div>
          <div v-else class="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              v-for="template in templates"
              :key="template.id"
              @click="applyTemplate(template)"
              type="button"
              :class="[
                'min-h-24 rounded border p-3 text-left transition',
                selectedTemplateId === template.id
                  ? 'border-blue-300 bg-blue-50 shadow-sm'
                  : 'border-slate-200 hover:border-blue-200 hover:bg-slate-50',
              ]"
            >
              <span class="flex items-start justify-between gap-2">
                <span class="min-w-0">
                  <span class="block truncate text-sm font-semibold text-slate-900">{{ template.name }}</span>
                  <span
                    :class="template.source === 'custom' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'"
                    class="mt-1 inline-flex rounded px-1.5 py-0.5 text-[11px]"
                  >
                    {{ template.source === 'custom' ? '自定义' : '内置' }}
                  </span>
                </span>
                <span
                  v-if="template.editable"
                  @click.stop="removeTemplate(template)"
                  class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                  title="删除模板"
                >
                  <Trash2 :size="14" />
                </span>
              </span>
              <span class="mt-1 block text-xs leading-5 text-slate-500">{{ template.description }}</span>
              <span class="mt-2 flex flex-wrap gap-1">
                <span v-if="template.rag_enabled === 1" class="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] text-emerald-700">RAG</span>
                <span v-if="template.memory_enabled === 1" class="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700">记忆</span>
                <span v-if="template.skill_names.length" class="rounded bg-violet-50 px-1.5 py-0.5 text-[11px] text-violet-700">Skill</span>
              </span>
            </button>
          </div>
          <p v-if="selectedTemplateId && missingTemplateSkillNames.length" class="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            模板建议绑定的 Skill 未找到：{{ missingTemplateSkillNames.join('、') }}。可以先保存 Agent，之后在 Skill 管理中补充。
          </p>
        </section>

        <div class="mb-4 grid grid-cols-3 gap-2 text-xs">
          <div :class="stepClass(Boolean(form.name.trim()))">
            <span class="flex h-6 w-6 items-center justify-center rounded bg-white">
              <Bot :size="14" />
            </span>
            <span>基础信息</span>
          </div>
          <div :class="stepClass(modelReady)">
            <span class="flex h-6 w-6 items-center justify-center rounded bg-white">
              <KeyRound :size="14" />
            </span>
            <span>模型 Key</span>
          </div>
          <div :class="stepClass(ragReady)">
            <span class="flex h-6 w-6 items-center justify-center rounded bg-white">
              <Database :size="14" />
            </span>
            <span>知识库</span>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <section class="md:col-span-2 rounded-lg border border-slate-200 p-4">
            <div class="mb-3 flex items-center gap-2">
              <Bot :size="16" class="text-slate-500" />
              <h3 class="text-sm font-semibold text-slate-800">基础信息</h3>
            </div>
            <label class="mb-1 block text-xs font-medium text-slate-600">名称</label>
            <input
              v-model="form.name"
              class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
              placeholder="例如：论文写作助手"
            />
          </section>

          <section class="md:col-span-2 rounded-lg border border-slate-200 p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <KeyRound :size="16" class="text-slate-500" />
                <h3 class="text-sm font-semibold text-slate-800">模型调用</h3>
              </div>
              <button
                @click="router.push('/llm-configs')"
                type="button"
                class="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Settings :size="13" />
                配置 Key
              </button>
            </div>

            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs font-medium text-slate-600">模型</label>
            <input
              v-model="form.model_name"
              list="agent-model-options"
              class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
              placeholder="glm-4"
            />
            <datalist id="agent-model-options">
              <option value="glm-4" />
              <option value="glm-4-plus" />
              <option value="deepseek-chat" />
              <option value="gpt-4o" />
              <option value="gpt-4o-mini" />
            </datalist>
                <p :class="modelReady ? 'text-emerald-600' : 'text-amber-600'" class="mt-1 text-xs">
                  {{ modelReady ? '当前用户已保存该模型 Key' : '当前用户还没有保存该模型 Key' }}
                </p>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">温度：{{ form.temperature }}</label>
            <input v-model.number="form.temperature" type="range" min="0" max="100" class="h-10 w-full" />
                <div class="mt-1 flex justify-between text-xs text-slate-400">
                  <span>稳定</span>
                  <span>发散</span>
                </div>
              </div>
            </div>
          </section>

          <section class="md:col-span-2 rounded-lg border border-slate-200 p-4">
            <div class="mb-3 flex items-center gap-2">
              <Database :size="16" class="text-slate-500" />
              <h3 class="text-sm font-semibold text-slate-800">能力开关</h3>
            </div>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label class="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
                <span>
                  <span class="block text-sm font-medium text-slate-800">知识库 RAG</span>
                  <span class="block text-xs text-slate-500">{{ ragReady ? '会在回答前检索知识库' : '需要先保存向量模型 Key' }}</span>
                </span>
                <input type="checkbox" v-model="ragEnabledBool" class="h-4 w-4" />
              </label>
              <label class="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
                <span>
                  <span class="block text-sm font-medium text-slate-800">长期记忆</span>
                  <span class="block text-xs text-slate-500">按对话沉淀摘要记忆</span>
                </span>
                <input type="checkbox" v-model="memoryEnabledBool" class="h-4 w-4" />
              </label>
            </div>
            <div v-if="ragEnabledBool && !ragReady" class="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              开启 RAG 后，上传和检索需要配置 embedding-3 或 text-embedding-3-small 这类向量模型 Key。
            </div>
          </section>

          <section class="md:col-span-2 rounded-lg border border-slate-200 p-4">
            <div class="mb-3 flex items-center gap-2">
              <FileText :size="16" class="text-slate-500" />
              <h3 class="text-sm font-semibold text-slate-800">提示词</h3>
            </div>
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div class="md:col-span-2">
                <label class="mb-1 block text-xs font-medium text-slate-600">角色设定</label>
                <textarea
                  v-model="form.role"
                  rows="3"
                  class="w-full resize-y rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
                  placeholder="这个 Agent 应该扮演什么角色"
                />
              </div>

              <div class="md:col-span-2">
                <label class="mb-1 block text-xs font-medium text-slate-600">任务说明</label>
                <textarea
                  v-model="form.task"
                  rows="3"
                  class="w-full resize-y rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
                  placeholder="它主要要完成什么任务"
                />
              </div>

              <div>
                <label class="mb-1 block text-xs font-medium text-slate-600">约束</label>
                <textarea
                  v-model="form.constraints"
                  rows="3"
                  class="w-full resize-y rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
                  placeholder="边界、禁忌、注意事项"
                />
              </div>

              <div>
                <label class="mb-1 block text-xs font-medium text-slate-600">输出格式</label>
                <textarea
                  v-model="form.output"
                  rows="3"
                  class="w-full resize-y rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
                  placeholder="回答结构、格式、语气"
                />
              </div>
            </div>
          </section>

          <section class="md:col-span-2 rounded-lg border border-slate-200 p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <Zap :size="16" class="text-slate-500" />
                <h3 class="text-sm font-semibold text-slate-800">绑定 Skill</h3>
              </div>
              <span class="text-xs text-slate-400">{{ form.skill_ids.length }} 个已选</span>
            </div>
            <div class="max-h-44 overflow-y-auto rounded border border-slate-200 p-2">
              <label
                v-for="s in skills"
                :key="s.id"
                :class="[
                  'flex cursor-pointer items-center gap-3 rounded px-2 py-2 text-sm text-slate-700 hover:bg-slate-50',
                  skillValidationMap[s.id]?.ok === false ? 'bg-red-50/50' : '',
                ]"
              >
                <input
                  type="checkbox"
                  :value="s.id"
                  v-model="form.skill_ids"
                  :disabled="skillValidationMap[s.id]?.ok === false"
                  class="h-4 w-4"
                />
                <span class="min-w-0 flex-1">
                  <span class="block truncate">{{ s.name }}</span>
                  <span class="block truncate text-xs text-slate-400">{{ skillSummary(s.id) }}</span>
                </span>
                <button
                  @click.prevent="openSkillPreview(s.id)"
                  type="button"
                  class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  title="查看校验结果"
                >
                  <Info :size="14" />
                </button>
                <span :class="s.is_public === 1 ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'" class="rounded px-2 py-0.5 text-xs">
                  {{ s.is_public === 1 ? '公开' : '私有' }}
                </span>
              </label>
              <div v-if="skills.length === 0" class="py-6 text-center text-sm text-slate-400">暂无 Skill，可稍后在 Skill 管理中创建</div>
            </div>
            <div v-if="selectedInvalidSkillNames.length" class="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              已选 Skill 中存在不可用项：{{ selectedInvalidSkillNames.join('、') }}
            </div>
          </section>
          </div>
      </main>

      <footer class="border-t border-slate-200 px-5 py-4">
        <div class="flex items-center justify-between gap-3">
          <p v-if="errorMsg" class="text-sm text-red-600">{{ errorMsg }}</p>
          <span v-else class="text-xs text-slate-400">保存后会同步更新 Agent 的提示词文件和 Skill 绑定</span>
          <div class="flex shrink-0 justify-end gap-2">
            <button
              v-if="!agent"
              @click="saveCurrentAsTemplate"
              :disabled="!form.name.trim() || savingTemplate"
              class="inline-flex items-center gap-1 rounded border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:text-slate-300"
            >
              <BookmarkPlus :size="14" />
              {{ savingTemplate ? '保存模板中...' : '保存为模板' }}
            </button>
            <button
              @click="$emit('close')"
              class="rounded border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              @click="submit"
              :disabled="!form.name.trim() || submitting"
              class="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-300"
            >
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </footer>
    </div>

    <div v-if="previewSkillValidation" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4" @click.self="previewSkillValidation = null">
      <div class="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <div>
            <h3 class="text-sm font-semibold text-slate-900">{{ previewSkillValidation.name }}</h3>
            <p class="text-xs text-slate-500">{{ previewSkillValidation.config_file }}</p>
          </div>
          <button @click="previewSkillValidation = null" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100">
            <X :size="16" />
          </button>
        </header>
        <main class="space-y-3 p-5 text-sm">
          <div :class="previewSkillValidation.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'" class="rounded border px-3 py-2">
            {{ previewSkillValidation.ok ? '该 Skill 可以被当前用户绑定和运行' : '该 Skill 当前不可用' }}
          </div>
          <div>
            <p class="mb-1 text-xs font-medium text-slate-500">可用工具</p>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="tool in previewSkillValidation.tool_names" :key="tool" class="rounded bg-blue-50 px-2 py-1 text-xs text-blue-700">{{ tool }}</span>
              <span v-if="previewSkillValidation.tool_names.length === 0" class="text-xs text-slate-400">无</span>
            </div>
          </div>
          <div v-if="previewSkillValidation.errors.length">
            <p class="mb-1 text-xs font-medium text-red-600">错误</p>
            <p v-for="err in previewSkillValidation.errors" :key="err" class="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{{ err }}</p>
          </div>
          <div v-if="previewSkillValidation.warnings.length">
            <p class="mb-1 text-xs font-medium text-amber-600">提醒</p>
            <p v-for="warn in previewSkillValidation.warnings" :key="warn" class="rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">{{ warn }}</p>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BookmarkPlus, Bot, Database, FileText, Info, KeyRound, Settings, Sparkles, Trash2, X, Zap } from 'lucide-vue-next'
import * as agentApi from '../api/agent'
import type { AgentTemplate } from '../api/agent'
import * as llmConfigApi from '../api/llmConfig'
import * as skillApi from '../api/skill'
import type { LlmConfig } from '../api/llmConfig'
import type { SkillValidation } from '../api/skill'
import { getErrorMessage } from '../utils/request'
import { toastSuccess } from '../utils/toast'

const props = defineProps<{
  agent: any
  skills: any[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'success', payload?: { agentId?: number; created: boolean }): void
}>()

const router = useRouter()

const emptyForm = () => ({
  name: '',
  model_name: 'glm-4',
  temperature: 70,
  role: '',
  task: '',
  constraints: '',
  output: '',
  skill_ids: [] as number[],
  rag_enabled: 0,
  memory_enabled: 1,
})

const form = ref(emptyForm())
const submitting = ref(false)
const errorMsg = ref('')
const configs = ref<LlmConfig[]>([])
const skillValidationMap = ref<Record<number, SkillValidation>>({})
const previewSkillValidation = ref<SkillValidation | null>(null)
const templates = ref<AgentTemplate[]>([])
const templateLoading = ref(false)
const savingTemplate = ref(false)
const selectedTemplateId = ref('')
const missingTemplateSkillNames = ref<string[]>([])

const normalizedModelName = computed(() => form.value.model_name.trim().toLowerCase())
const configuredModelNames = computed(() => new Set(configs.value.map((config) => config.model_name.toLowerCase())))
const modelReady = computed(() => {
  const model = normalizedModelName.value
  return Boolean(model && configuredModelNames.value.has(model))
})
const ragReady = computed(() => {
  if (!ragEnabledBool.value) return true
  return configs.value.some((config) => {
    const model = config.model_name.toLowerCase()
    return model.includes('embedding') || model.startsWith('baai/')
  })
})
const selectedInvalidSkillNames = computed(() => form.value.skill_ids
  .map((id) => skillValidationMap.value[id])
  .filter((validation) => validation && !validation.ok)
  .map((validation) => validation.name))

const ragEnabledBool = computed<boolean>({
  get: () => form.value.rag_enabled === 1,
  set: (v) => { form.value.rag_enabled = v ? 1 : 0 },
})

const memoryEnabledBool = computed<boolean>({
  get: () => form.value.memory_enabled === 1,
  set: (v) => { form.value.memory_enabled = v ? 1 : 0 },
})

const stepClass = (done: boolean) => [
  'flex min-w-0 items-center gap-2 rounded border px-3 py-2',
  done ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500',
]

const loadConfigs = async () => {
  try {
    configs.value = await llmConfigApi.listConfigs()
  } catch {
    configs.value = []
  }
}

const loadTemplates = async () => {
  templateLoading.value = true
  try {
    templates.value = await agentApi.listAgentTemplates()
  } catch {
    templates.value = []
  } finally {
    templateLoading.value = false
  }
}

const loadSkillValidations = async () => {
  const entries = await Promise.all(props.skills.map(async (skill) => {
    try {
      return [skill.id, await skillApi.validateSkill(skill.id)] as const
    } catch {
      return [skill.id, {
        ok: false,
        errors: ['无法校验该 Skill，可能不存在或无权限访问'],
        warnings: [],
        tool_names: [],
        missing_tool_names: [],
        system_prompt_ready: false,
        permissions: { network: false, file_read: [], exec: false },
        resources: [],
        resource_count: 0,
        allowed_resource_count: 0,
        skill_id: skill.id,
        name: skill.name,
        config_file: skill.config_file,
        is_public: skill.is_public,
      }] as const
    }
  }))
  skillValidationMap.value = Object.fromEntries(entries)
  form.value.skill_ids = form.value.skill_ids.filter((id) => skillValidationMap.value[id]?.ok !== false)
}

const skillIdsByNames = (skillNames: string[]) => {
  const normalizedNames = skillNames.map((name) => name.trim()).filter(Boolean)
  const ids: number[] = []
  const missing: string[] = []
  normalizedNames.forEach((name) => {
    const matched = props.skills.find((skill) => skill.name === name)
    if (matched) ids.push(matched.id)
    else missing.push(name)
  })
  missingTemplateSkillNames.value = missing
  return ids
}

const applyTemplate = (template: AgentTemplate) => {
  selectedTemplateId.value = template.id
  form.value = {
    name: template.name,
    model_name: template.model_name,
    temperature: template.temperature,
    role: template.role,
    task: template.task,
    constraints: template.constraints,
    output: template.output,
    skill_ids: skillIdsByNames(template.skill_names),
    rag_enabled: template.rag_enabled,
    memory_enabled: template.memory_enabled,
  }
  errorMsg.value = ''
}

const startBlank = () => {
  selectedTemplateId.value = ''
  missingTemplateSkillNames.value = []
  form.value = emptyForm()
  errorMsg.value = ''
}

const selectedSkillNames = () => {
  const skillMap = new Map(props.skills.map((skill) => [skill.id, skill.name]))
  return form.value.skill_ids
    .map((id) => skillMap.get(id))
    .filter((name): name is string => Boolean(name))
}

const saveCurrentAsTemplate = async () => {
  if (!form.value.name.trim()) return
  savingTemplate.value = true
  errorMsg.value = ''
  try {
    const template = await agentApi.createAgentTemplate({
      name: form.value.name.trim(),
      description: `${form.value.name.trim()}的自定义配置`,
      model_name: form.value.model_name.trim() || 'glm-4',
      role: form.value.role,
      task: form.value.task,
      constraints: form.value.constraints,
      output: form.value.output,
      rag_enabled: form.value.rag_enabled,
      memory_enabled: form.value.memory_enabled,
      temperature: Math.min(100, Math.max(0, Number(form.value.temperature) || 0)),
      skill_names: selectedSkillNames(),
    })
    templates.value = [template, ...templates.value]
    selectedTemplateId.value = template.id
    toastSuccess('已保存为自定义模板')
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '保存模板失败')
  } finally {
    savingTemplate.value = false
  }
}

const removeTemplate = async (template: AgentTemplate) => {
  if (!template.editable) return
  if (!confirm(`确认删除模板「${template.name}」？`)) return
  try {
    await agentApi.deleteAgentTemplate(template.id)
    templates.value = templates.value.filter((item) => item.id !== template.id)
    if (selectedTemplateId.value === template.id) {
      selectedTemplateId.value = ''
    }
    toastSuccess('模板已删除')
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '删除模板失败')
  }
}

const skillSummary = (skillId: number) => {
  const validation = skillValidationMap.value[skillId]
  if (!validation) return '校验中...'
  if (!validation.ok) return validation.errors[0] || '不可用'
  if (validation.tool_names.length === 0) return '提示词 Skill，无工具'
  return `工具：${validation.tool_names.join('、')}`
}

const openSkillPreview = (skillId: number) => {
  previewSkillValidation.value = skillValidationMap.value[skillId] || null
}

watch(() => props.agent, (a: any) => {
  if (!a) {
    form.value = emptyForm()
    errorMsg.value = ''
    selectedTemplateId.value = ''
    missingTemplateSkillNames.value = []
    return
  }
  const prompt = a.prompt || {}
  form.value = {
    name: a.name || '',
    model_name: a.model_name || 'glm-4',
    temperature: a.temperature ?? 70,
    role: prompt.role || a.role || '',
    task: prompt.task || a.task || '',
    constraints: prompt.constraints || a.constraints || '',
    output: prompt.output || a.output || '',
    skill_ids: (a.skills || []).map((s: any) => s.id),
    rag_enabled: a.rag_enabled ?? 0,
    memory_enabled: a.memory_enabled ?? 1,
  }
  errorMsg.value = ''
  selectedTemplateId.value = ''
  missingTemplateSkillNames.value = []
}, { immediate: true })

const submit = async () => {
  if (!form.value.name.trim()) return
  if (!modelReady.value) {
    errorMsg.value = `请先在模型 Key 页面配置「${form.value.model_name.trim() || '当前模型'}」的 API Key`
    return
  }
  if (!ragReady.value) {
    errorMsg.value = '开启 RAG 前请先配置向量模型 Key'
    return
  }
  if (selectedInvalidSkillNames.value.length) {
    errorMsg.value = `请先移除不可用 Skill：${selectedInvalidSkillNames.value.join('、')}`
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    const payload = {
      ...form.value,
      name: form.value.name.trim(),
      model_name: form.value.model_name.trim() || 'glm-4',
      temperature: Math.min(100, Math.max(0, Number(form.value.temperature) || 0)),
    }
    if (props.agent) {
      await agentApi.updateAgent(props.agent.id, payload)
      emit('success', { agentId: props.agent.id, created: false })
    } else {
      const result = await agentApi.createAgent(payload)
      emit('success', { agentId: result.agent_id, created: true })
    }
    emit('close')
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadConfigs(), loadSkillValidations(), loadTemplates()])
})
watch(() => props.skills, loadSkillValidations, { deep: true })
</script>
