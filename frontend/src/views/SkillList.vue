<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <div class="flex items-center gap-3">
        <button
          @click="router.push('/agents')"
          class="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50"
          title="返回 Agent 列表"
        >
          <ArrowLeft :size="16" />
        </button>
        <div>
          <h1 class="text-base font-semibold text-slate-900">Skill 管理</h1>
          <p class="text-xs text-slate-500">创建、导入并绑定可被 Agent 加载的能力包</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <input
          ref="importInput"
          type="file"
          class="hidden"
          accept=".zip,.yml,.yaml"
          @change="handleImportSelect"
        />
        <button
          @click="importInput?.click()"
          :disabled="importing"
          class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
        >
          <Upload :size="15" />
          {{ importing ? '导入中...' : '导入 Skill' }}
        </button>
        <button
          @click="openCreate"
          class="inline-flex items-center gap-2 rounded bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-700"
        >
          <Plus :size="15" />
          新建 Skill
        </button>
        <button
          @click="openTemplateCreate"
          class="inline-flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <Plus :size="15" />
          新建模板
        </button>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-6">
      <div class="mx-auto max-w-6xl">
        <section class="mb-5">
          <div class="mb-2 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-slate-900">Skill 模板</h2>
            <span class="text-xs text-slate-500">内置模板可直接使用，用户模板可编辑复用</span>
          </div>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="template in templates"
              :key="template.filename"
              class="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <h3 class="truncate text-sm font-semibold text-slate-900">{{ template.name }}</h3>
                  <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">{{ template.description || template.filename }}</p>
                </div>
                <span :class="template.editable ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'" class="shrink-0 rounded px-2 py-1 text-xs">
                  {{ template.editable ? '用户模板' : '内置' }}
                </span>
              </div>
              <p class="mt-3 truncate text-xs text-slate-400">{{ (template.tool_names || []).join(' / ') || '未配置工具' }}</p>
              <div class="mt-4 flex justify-end gap-2 border-t border-slate-100 pt-3">
                <button
                  @click="createFromTemplate(template)"
                  class="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                >
                  使用
                </button>
                <button
                  v-if="template.editable"
                  @click="openTemplateEdit(template)"
                  class="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                >
                  编辑
                </button>
                <button
                  v-if="template.editable"
                  @click="handleTemplateDelete(template)"
                  class="rounded border border-red-100 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                >
                  删除
                </button>
              </div>
            </article>
          </div>
        </section>

        <div class="mb-4 flex items-center justify-between">
          <div class="inline-flex rounded border border-slate-200 bg-white p-1">
            <button
              @click="activeTab = 'mine'"
              :class="activeTab === 'mine' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'"
              class="rounded px-3 py-1.5 text-sm"
            >
              我的 Skill
            </button>
            <button
              @click="activeTab = 'public'"
              :class="activeTab === 'public' ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'"
              class="rounded px-3 py-1.5 text-sm"
            >
              公开 Skill
            </button>
          </div>
          <div class="flex items-center gap-3">
            <span v-if="importError" class="text-xs text-red-600">{{ importError }}</span>
            <button @click="reload" class="text-xs text-slate-500 hover:text-slate-900">刷新</button>
          </div>
        </div>

        <div v-if="shownSkills.length === 0" class="rounded-lg border border-dashed border-slate-300 bg-white py-16 text-center text-sm text-slate-500">
          {{ activeTab === 'mine' ? '你还没有创建 Skill。' : '暂无公开 Skill。' }}
        </div>

        <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="skill in shownSkills"
            :key="skill.id"
            class="bg-white border border-slate-200 rounded-lg p-4 hover:border-slate-300 hover:shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 items-center gap-3">
                <span class="inline-flex h-9 w-9 items-center justify-center rounded bg-violet-50 text-violet-700">
                  <Zap :size="18" />
                </span>
                <div class="min-w-0">
                  <h2 class="truncate text-sm font-semibold text-slate-900">{{ skill.name }}</h2>
                  <p class="truncate text-xs text-slate-500">{{ skill.config_file }}</p>
                </div>
              </div>
              <span :class="skill.is_public === 1 ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'" class="shrink-0 rounded px-2 py-1 text-xs">
                {{ skill.is_public === 1 ? '公开' : '私有' }}
              </span>
            </div>

            <p class="mt-4 min-h-10 text-sm leading-relaxed text-slate-600">{{ skill.description || '暂无描述' }}</p>
            <div class="mt-3 rounded border px-3 py-2 text-xs" :class="validationBoxClass(skill.id)">
              <div class="flex items-center justify-between gap-2">
                <span class="inline-flex min-w-0 items-center gap-1.5">
                  <component :is="validationIcon(skill.id)" :size="14" class="shrink-0" />
                  <span class="truncate">{{ validationText(skill.id) }}</span>
                </span>
                <button
                  @click="openValidationPreview(skill.id)"
                  class="shrink-0 rounded px-1.5 py-0.5 hover:bg-white/70"
                  title="查看校验详情"
                >
                  详情
                </button>
              </div>
              <div v-if="validationMap[skill.id]?.tool_names?.length" class="mt-2 flex flex-wrap gap-1">
                <span
                  v-for="toolName in validationMap[skill.id].tool_names"
                  :key="toolName"
                  class="rounded bg-white/70 px-1.5 py-0.5 text-[11px]"
                >
                  {{ toolName }}
                </span>
              </div>
              <div class="mt-2 flex flex-wrap gap-1">
                <span class="rounded bg-white/70 px-1.5 py-0.5 text-[11px]">
                  资源 {{ validationMap[skill.id]?.allowed_resource_count || 0 }}/{{ validationMap[skill.id]?.resource_count || 0 }}
                </span>
                <span
                  v-if="validationMap[skill.id]?.permissions?.network"
                  class="rounded bg-white/70 px-1.5 py-0.5 text-[11px]"
                >
                  网络
                </span>
              </div>
            </div>

            <div class="mt-4 flex justify-end gap-2 border-t border-slate-100 pt-3">
              <button
                @click="openEdit(skill)"
                class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                title="编辑"
              >
                <Pencil :size="15" />
              </button>
              <button
                @click="handleExport(skill)"
                class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-blue-50 hover:text-blue-700"
                title="导出"
              >
                <Download :size="15" />
              </button>
              <button
                @click="handleDelete(skill)"
                class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-red-50 hover:text-red-600"
                title="删除"
              >
                <Trash2 :size="15" />
              </button>
            </div>
          </article>
        </div>
      </div>
    </main>

    <div v-if="showDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="closeDialog">
      <div class="w-full max-w-2xl rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <h2 class="text-base font-semibold text-slate-900">{{ editing ? '编辑 Skill' : '新建 Skill' }}</h2>
          <button @click="closeDialog" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            <X :size="16" />
          </button>
        </header>

        <main class="max-h-[72vh] space-y-4 overflow-y-auto p-5">
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs font-medium text-slate-600">名称</label>
              <input v-model="form.name" class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-violet-500" placeholder="例如：合同审阅助手" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-slate-600">创建方式</label>
              <select
                v-model="form.template_filename"
                :disabled="!!editing"
                class="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-violet-500 disabled:bg-slate-100"
              >
                <option value="">自定义 Skill</option>
                <option v-for="t in templates" :key="t.filename" :value="t.filename">
                  从模板创建：{{ t.name }}
                </option>
              </select>
            </div>
          </div>

          <div v-if="!editing" class="grid grid-cols-1 gap-2 md:grid-cols-2">
            <button
              type="button"
              @click="selectBlankTemplate"
              :class="!form.template_filename ? 'border-violet-500 bg-violet-50' : 'border-slate-200 bg-white hover:bg-slate-50'"
              class="rounded border p-3 text-left"
            >
              <span class="block text-sm font-medium text-slate-900">自定义 Skill</span>
              <span class="mt-1 block text-xs leading-relaxed text-slate-500">从零选择工具、填写指令，适合完全自定义能力。</span>
            </button>
            <button
              v-for="template in templates"
              :key="template.filename"
              type="button"
              @click="applyTemplate(template)"
              :class="form.template_filename === template.filename ? 'border-violet-500 bg-violet-50' : 'border-slate-200 bg-white hover:bg-slate-50'"
              class="rounded border p-3 text-left"
            >
              <span class="block text-sm font-medium text-slate-900">{{ template.name }}</span>
              <span class="mt-1 line-clamp-2 block text-xs leading-relaxed text-slate-500">{{ template.description || template.filename }}</span>
              <span class="mt-2 block truncate text-xs text-slate-400">{{ (template.tool_names || []).join(' / ') || '未配置工具' }}</span>
            </button>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">描述</label>
            <textarea v-model="form.description" rows="3" class="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-violet-500" placeholder="说明这个 Skill 提供的能力" />
          </div>

          <div>
            <div class="mb-2 flex items-center justify-between">
              <label class="block text-xs font-medium text-slate-600">可用工具</label>
              <span class="text-xs text-slate-400">选择后会写入 Skill 配置</span>
            </div>
            <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
              <label
                v-for="tool in tools"
                :key="tool.name"
                class="flex items-start gap-2 rounded border border-slate-200 px-3 py-2"
              >
                <input v-model="form.tool_names" type="checkbox" :value="tool.name" class="mt-1 h-4 w-4" />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-800">{{ tool.name }}</span>
                  <span class="line-clamp-2 block text-xs leading-relaxed text-slate-500">{{ tool.description }}</span>
                </span>
              </label>
            </div>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">Skill 指令</label>
            <textarea
              v-model="form.system_prompt"
              rows="7"
              class="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-violet-500"
              placeholder="写下这个 Skill 的工作流程、约束、输出格式。"
            />
          </div>

          <div class="rounded border border-slate-200 p-3">
            <div class="mb-3 flex items-center justify-between">
              <div>
                <p class="text-xs font-medium text-slate-600">权限与资源</p>
                <p class="mt-1 text-xs text-slate-400">每行一个 resources 内的相对路径</p>
              </div>
              <label class="flex items-center gap-2 text-xs text-slate-600">
                <input type="checkbox" v-model="form.permission_network" class="h-4 w-4" />
                需要网络
              </label>
            </div>
            <textarea
              v-model="form.permission_file_read"
              rows="4"
              class="w-full resize-none rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-violet-500"
              placeholder="例如：guide.md&#10;examples/sample.json"
            />
            <div v-if="form.resources.length" class="mt-3 space-y-1">
              <p class="text-xs font-medium text-slate-500">已随 Skill 导入的资源</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="resource in form.resources"
                  :key="resource.path"
                  type="button"
                  @click="toggleResource(resource.path)"
                  :class="isResourceAllowed(resource.path) ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'"
                  class="rounded px-2 py-1 text-xs"
                  :title="resource.exists ? resource.path : '文件不存在'"
                >
                  {{ resource.path }}
                </button>
              </div>
            </div>
          </div>

          <label class="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
            <span>
              <span class="block text-sm font-medium text-slate-800">公开 Skill</span>
              <span class="block text-xs text-slate-500">其他用户可以在公开列表中使用</span>
            </span>
            <input type="checkbox" v-model="isPublicBool" class="h-4 w-4" />
          </label>
        </main>

        <footer class="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <p v-if="errorMsg" class="text-sm text-red-600">{{ errorMsg }}</p>
          <span v-else class="text-xs text-slate-400">{{ editing ? '保存后会同步更新 Skill 配置文件。' : '保存后会生成一个用户专属 Skill 配置文件。' }}</span>
          <div class="flex shrink-0 gap-2">
            <button @click="closeDialog" class="rounded border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">取消</button>
            <button
              @click="saveCurrentAsTemplate"
              :disabled="submitting || !form.name.trim() || form.tool_names.length === 0 || !form.system_prompt.trim()"
              class="rounded border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
            >
              另存为模板
            </button>
            <button
              @click="submit"
              :disabled="submitting || !form.name.trim() || form.tool_names.length === 0 || (!editing && !form.template_filename && !form.system_prompt.trim())"
              class="rounded bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:bg-violet-300"
            >
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </footer>
      </div>
    </div>

    <div v-if="showTemplateDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="closeTemplateDialog">
      <div class="w-full max-w-2xl rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <h2 class="text-base font-semibold text-slate-900">{{ templateEditing ? '编辑模板' : '新建模板' }}</h2>
          <button @click="closeTemplateDialog" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            <X :size="16" />
          </button>
        </header>

        <main class="max-h-[72vh] space-y-4 overflow-y-auto p-5">
          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">模板名称</label>
            <input v-model="templateForm.name" class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-violet-500" placeholder="例如：投研分析模板" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">模板描述</label>
            <textarea v-model="templateForm.description" rows="3" class="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-violet-500" placeholder="说明这个模板适合什么场景" />
          </div>
          <div>
            <div class="mb-2 flex items-center justify-between">
              <label class="block text-xs font-medium text-slate-600">模板工具</label>
              <span class="text-xs text-slate-400">创建 Skill 时会默认带出</span>
            </div>
            <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
              <label v-for="tool in tools" :key="tool.name" class="flex items-start gap-2 rounded border border-slate-200 px-3 py-2">
                <input v-model="templateForm.tool_names" type="checkbox" :value="tool.name" class="mt-1 h-4 w-4" />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-800">{{ tool.name }}</span>
                  <span class="line-clamp-2 block text-xs leading-relaxed text-slate-500">{{ tool.description }}</span>
                </span>
              </label>
            </div>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-slate-600">模板指令</label>
            <textarea v-model="templateForm.system_prompt" rows="8" class="w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-violet-500" placeholder="写下默认工作流程、约束和输出格式" />
          </div>
        </main>

        <footer class="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-4">
          <p v-if="templateErrorMsg" class="text-sm text-red-600">{{ templateErrorMsg }}</p>
          <span v-else class="text-xs text-slate-400">模板会保存为当前用户专属配置。</span>
          <div class="flex shrink-0 gap-2">
            <button @click="closeTemplateDialog" class="rounded border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">取消</button>
            <button
              @click="submitTemplate"
              :disabled="templateSubmitting || !templateForm.name.trim() || templateForm.tool_names.length === 0 || !templateForm.system_prompt.trim()"
              class="rounded bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:bg-violet-300"
            >
              {{ templateSubmitting ? '保存中...' : '保存模板' }}
            </button>
          </div>
        </footer>
      </div>
    </div>

    <div v-if="previewValidation" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4" @click.self="previewValidation = null">
      <div class="w-full max-w-lg rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-slate-900">{{ previewValidation.name }}</h2>
            <p class="truncate text-xs text-slate-500">{{ previewValidation.config_file }}</p>
          </div>
          <button @click="previewValidation = null" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            <X :size="16" />
          </button>
        </header>
        <main class="space-y-4 p-5">
          <div :class="previewValidation.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'" class="rounded border px-3 py-2 text-sm">
            {{ previewValidation.ok ? '该 Skill 当前可被 Agent 正常加载' : '该 Skill 当前不可用' }}
          </div>
          <div>
            <p class="mb-2 text-xs font-medium text-slate-500">工具</p>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="toolName in previewValidation.tool_names" :key="toolName" class="rounded bg-blue-50 px-2 py-1 text-xs text-blue-700">{{ toolName }}</span>
              <span v-if="previewValidation.tool_names.length === 0" class="text-xs text-slate-400">没有可用工具</span>
            </div>
          </div>
          <div>
            <p class="mb-2 text-xs font-medium text-slate-500">Prompt</p>
            <span :class="previewValidation.system_prompt_ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'" class="rounded px-2 py-1 text-xs">
              {{ previewValidation.system_prompt_ready ? '已填写' : '为空' }}
            </span>
          </div>
          <div>
            <p class="mb-2 text-xs font-medium text-slate-500">权限与资源</p>
            <div class="flex flex-wrap gap-1.5">
              <span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                网络 {{ previewValidation.permissions?.network ? '允许' : '关闭' }}
              </span>
              <span class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                资源 {{ previewValidation.allowed_resource_count }}/{{ previewValidation.resource_count }}
              </span>
            </div>
            <div v-if="previewValidation.resources?.length" class="mt-2 max-h-28 overflow-y-auto rounded border border-slate-200 p-2">
              <p v-for="resource in previewValidation.resources" :key="resource.path" class="text-xs text-slate-500">
                {{ resource.allowed ? '已允许' : '未允许' }} · {{ resource.path }} · {{ resource.exists ? '存在' : '缺失' }}
              </p>
            </div>
          </div>
          <div v-if="previewValidation.errors.length" class="space-y-2">
            <p class="text-xs font-medium text-red-600">错误</p>
            <p v-for="err in previewValidation.errors" :key="err" class="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{{ err }}</p>
          </div>
          <div v-if="previewValidation.warnings.length" class="space-y-2">
            <p class="text-xs font-medium text-amber-600">提醒</p>
            <p v-for="warn in previewValidation.warnings" :key="warn" class="rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">{{ warn }}</p>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock3, Download, Pencil, Plus, Trash2, Upload, X, Zap } from 'lucide-vue-next'
import * as skillApi from '../api/skill'
import type { Skill, SkillTemplate, SkillTool, SkillValidation } from '../api/skill'
import { toastSuccess } from '../utils/toast'
import { getErrorMessage } from '../utils/request'

const router = useRouter()
const mySkills = ref<Skill[]>([])
const publicSkills = ref<Skill[]>([])
const templates = ref<SkillTemplate[]>([])
const tools = ref<SkillTool[]>([])
const activeTab = ref<'mine' | 'public'>('mine')
const showDialog = ref(false)
const editing = ref<Skill | null>(null)
const submitting = ref(false)
const errorMsg = ref('')
const importing = ref(false)
const importError = ref('')
const importInput = ref<HTMLInputElement | null>(null)
const showTemplateDialog = ref(false)
const templateEditing = ref<SkillTemplate | null>(null)
const templateSubmitting = ref(false)
const templateErrorMsg = ref('')
const validationMap = ref<Record<number, SkillValidation>>({})
const validating = ref(false)
const previewValidation = ref<SkillValidation | null>(null)

const form = ref({
  name: '',
  description: '',
  template_filename: '',
  is_public: 0,
  system_prompt: '',
  tool_names: [] as string[],
  permission_network: false,
  permission_file_read: '',
  resources: [] as skillApi.SkillResource[],
})

const templateForm = ref({
  name: '',
  description: '',
  system_prompt: '',
  tool_names: [] as string[],
})

const shownSkills = computed(() => activeTab.value === 'mine' ? mySkills.value : publicSkills.value)
const isPublicBool = computed<boolean>({
  get: () => form.value.is_public === 1,
  set: (v) => { form.value.is_public = v ? 1 : 0 },
})

const loadValidations = async (skills: Skill[]) => {
  validating.value = true
  try {
    const entries = await Promise.all(skills.map(async (skill) => {
      try {
        return [skill.id, await skillApi.validateSkill(skill.id)] as const
      } catch (e: any) {
        return [skill.id, {
          ok: false,
          errors: [getErrorMessage(e, '无法校验该 Skill')],
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
    validationMap.value = Object.fromEntries(entries)
  } finally {
    validating.value = false
  }
}

const validationText = (skillId: number) => {
  const validation = validationMap.value[skillId]
  if (!validation || validating.value) return '校验中...'
  if (!validation.ok) return validation.errors[0] || '不可用'
  if (validation.warnings.length) return validation.warnings[0]
  return validation.tool_names.length ? '可正常加载' : '提示词 Skill'
}

const validationBoxClass = (skillId: number) => {
  const validation = validationMap.value[skillId]
  if (!validation || validating.value) return 'border-slate-200 bg-slate-50 text-slate-500'
  if (!validation.ok) return 'border-red-200 bg-red-50 text-red-700'
  if (validation.warnings.length) return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

const validationIcon = (skillId: number) => {
  const validation = validationMap.value[skillId]
  if (!validation || validating.value) return Clock3
  if (!validation.ok) return AlertTriangle
  if (validation.warnings.length) return AlertTriangle
  return CheckCircle2
}

const openValidationPreview = (skillId: number) => {
  previewValidation.value = validationMap.value[skillId] || null
}

watch(() => form.value.template_filename, (filename) => {
  if (editing.value || !filename) return
  const template = templates.value.find((item) => item.filename === filename)
  if (template) applyTemplate(template)
})

const applyTemplate = (template: SkillTemplate) => {
  form.value.template_filename = template.filename
  form.value.tool_names = [...(template.tool_names || [])]
  form.value.description = template.description || form.value.description
  form.value.system_prompt = template.system_prompt || form.value.system_prompt
}

const createFromTemplate = (template: SkillTemplate) => {
  editing.value = null
  form.value = {
    name: template.name,
    description: template.description || '',
    template_filename: template.filename,
    is_public: 0,
    system_prompt: template.system_prompt || '',
    tool_names: [...(template.tool_names || [])],
    permission_network: false,
    permission_file_read: '',
    resources: [],
  }
  errorMsg.value = ''
  showDialog.value = true
}

const selectBlankTemplate = () => {
  form.value.template_filename = ''
  form.value.tool_names = []
  form.value.system_prompt = ''
}

const reload = async () => {
  const [mine, pub, tpls, availableTools] = await Promise.all([
    skillApi.listUserSkills(),
    skillApi.listPublicSkills(),
    skillApi.listTemplates(),
    skillApi.listTools(),
  ])
  mySkills.value = mine
  publicSkills.value = pub
  templates.value = tpls
  tools.value = availableTools
  await loadValidations([...new Map([...mine, ...pub].map((skill) => [skill.id, skill])).values()])
}

const openCreate = () => {
  editing.value = null
  form.value = {
    name: '',
    description: '',
    template_filename: '',
    is_public: 0,
    system_prompt: '',
    tool_names: [],
    permission_network: false,
    permission_file_read: '',
    resources: [],
  }
  if (templates.value.length > 0) {
    const firstTemplate = templates.value[0]
    form.value.name = firstTemplate.name
    applyTemplate(firstTemplate)
  }
  errorMsg.value = ''
  showDialog.value = true
}

const openEdit = async (skill: Skill) => {
  editing.value = skill
  errorMsg.value = ''
  showDialog.value = true
  let detail = skill
  try {
    detail = await skillApi.getSkill(skill.id)
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '读取Skill配置失败')
  }
  form.value = {
    name: detail.name,
    description: detail.description || '',
    template_filename: '',
    is_public: detail.is_public,
    system_prompt: detail.config?.system_prompt || '',
    tool_names: [...(detail.config?.tool_names || [])],
    permission_network: Boolean(detail.config?.permissions?.network),
    permission_file_read: (detail.config?.permissions?.file_read || []).join('\n'),
    resources: [...(detail.config?.resources || [])],
  }
}

const closeDialog = () => {
  showDialog.value = false
  editing.value = null
}

const openTemplateCreate = () => {
  templateEditing.value = null
  templateForm.value = { name: '', description: '', system_prompt: '', tool_names: [] }
  templateErrorMsg.value = ''
  showTemplateDialog.value = true
}

const openTemplateEdit = async (template: SkillTemplate) => {
  templateEditing.value = template
  templateErrorMsg.value = ''
  showTemplateDialog.value = true
  let detail = template
  try {
    detail = await skillApi.getTemplate(template.filename)
  } catch (e: any) {
    templateErrorMsg.value = getErrorMessage(e, '读取模板失败')
  }
  templateForm.value = {
    name: detail.name,
    description: detail.description || '',
    system_prompt: detail.system_prompt || '',
    tool_names: [...(detail.tool_names || [])],
  }
}

const closeTemplateDialog = () => {
  showTemplateDialog.value = false
  templateEditing.value = null
}

const submitTemplate = async () => {
  templateSubmitting.value = true
  templateErrorMsg.value = ''
  try {
    const payload = {
      name: templateForm.value.name.trim(),
      description: templateForm.value.description,
      system_prompt: templateForm.value.system_prompt,
      tool_names: templateForm.value.tool_names,
    }
    if (templateEditing.value) {
      await skillApi.updateTemplate(templateEditing.value.filename, payload)
    } else {
      await skillApi.createTemplate(payload)
    }
    await reload()
    closeTemplateDialog()
  } catch (e: any) {
    templateErrorMsg.value = getErrorMessage(e, '保存模板失败')
  } finally {
    templateSubmitting.value = false
  }
}

const handleTemplateDelete = async (template: SkillTemplate) => {
  if (!confirm(`确认删除模板「${template.name}」？`)) return
  try {
    await skillApi.deleteTemplate(template.filename)
    await reload()
  } catch (e: any) {
    importError.value = getErrorMessage(e, '删除模板失败')
  }
}

const saveCurrentAsTemplate = async () => {
  submitting.value = true
  errorMsg.value = ''
  try {
    await skillApi.createTemplate({
      name: form.value.name.trim(),
      description: form.value.description,
      system_prompt: form.value.system_prompt,
      tool_names: form.value.tool_names,
    })
    await reload()
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '另存模板失败')
  } finally {
    submitting.value = false
  }
}

const submit = async () => {
  submitting.value = true
  errorMsg.value = ''
  try {
    if (editing.value) {
      await skillApi.updateSkill(editing.value.id, {
        name: form.value.name.trim(),
        description: form.value.description,
        is_public: form.value.is_public,
        system_prompt: form.value.system_prompt,
        tool_names: form.value.tool_names,
        permissions: buildPermissionsPayload(),
      })
    } else {
      await skillApi.createSkill({
        name: form.value.name.trim(),
        description: form.value.description,
        template_filename: form.value.template_filename,
        is_public: form.value.is_public,
        system_prompt: form.value.system_prompt,
        tool_names: form.value.tool_names,
        permissions: buildPermissionsPayload(),
      })
    }
    await reload()
    closeDialog()
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '保存失败')
  } finally {
    submitting.value = false
  }
}

const permissionFileReadList = () => form.value.permission_file_read
  .split('\n')
  .map((item) => item.trim().replaceAll('\\', '/'))
  .filter(Boolean)

const buildPermissionsPayload = () => ({
  network: form.value.permission_network,
  file_read: permissionFileReadList(),
  exec: false,
})

const isResourceAllowed = (path: string) => permissionFileReadList().includes(path)

const toggleResource = (path: string) => {
  const current = permissionFileReadList()
  const next = current.includes(path) ? current.filter((item) => item !== path) : [...current, path]
  form.value.permission_file_read = next.join('\n')
}

const handleDelete = async (skill: Skill) => {
  if (!confirm(`确认删除 Skill「${skill.name}」？已绑定该 Skill 的 Agent 会自动解绑。`)) return
  await skillApi.deleteSkill(skill.id)
  await reload()
}

const handleExport = async (skill: Skill) => {
  const blob = await skillApi.exportSkill(skill.id)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${skill.name}_${skill.id}.zip`
  link.click()
  URL.revokeObjectURL(url)
  toastSuccess('Skill 已导出')
}

const handleImportSelect = async (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  target.value = ''
  if (!file || importing.value) return
  importing.value = true
  importError.value = ''
  try {
    await skillApi.importSkill(file)
    activeTab.value = 'mine'
    await reload()
    toastSuccess('Skill 导入成功')
  } catch (err: any) {
    importError.value = getErrorMessage(err, '导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(reload)
</script>
