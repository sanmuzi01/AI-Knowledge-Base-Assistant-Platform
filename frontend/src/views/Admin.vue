<template>
  <div class="h-screen overflow-y-auto bg-slate-50 p-6">
    <div class="mx-auto max-w-7xl">
      <header class="mb-5 flex items-center justify-between">
        <div>
          <h1 class="text-base font-semibold text-slate-900">后台管理</h1>
          <p class="text-xs text-slate-500">用户、角色、任务和系统运行状态</p>
        </div>
        <button
          @click="loadAll"
          :disabled="loading"
          class="inline-flex items-center gap-2 rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
        >
          <RefreshCcw :size="15" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
      </header>

      <p v-if="errorMsg" class="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ errorMsg }}</p>

      <section class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-6">
        <article v-for="item in countItems" :key="item.key" class="rounded-lg border border-slate-200 bg-white p-4">
          <p class="text-xs text-slate-500">{{ item.label }}</p>
          <p class="mt-2 text-2xl font-semibold text-slate-900">{{ item.value }}</p>
        </article>
      </section>

      <div class="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(560px,1fr)_420px]">
        <section class="rounded-lg border border-slate-200 bg-white">
          <div class="flex h-12 items-center justify-between border-b border-slate-200 px-4">
            <h2 class="text-sm font-semibold text-slate-900">用户管控</h2>
            <span class="text-xs text-slate-400">{{ users.length }} 个用户</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[760px] text-left text-sm">
              <thead class="border-b border-slate-100 bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th class="px-4 py-3 font-medium">用户</th>
                  <th class="px-4 py-3 font-medium">角色</th>
                  <th class="px-4 py-3 font-medium">资源</th>
                  <th class="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="user in users" :key="user.id" class="border-b border-slate-100">
                  <td class="px-4 py-3">
                    <p class="font-medium text-slate-900">{{ user.name }}</p>
                    <p class="text-xs text-slate-400">ID {{ user.id }} · 年龄 {{ user.age ?? '-' }}</p>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="role in user.roles"
                        :key="role"
                        class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600"
                      >
                        {{ role }}
                      </span>
                      <span v-if="!user.roles.length" class="text-xs text-slate-400">无角色</span>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-xs text-slate-500">
                    助手 {{ user.agent_count }} · 能力 {{ user.skill_count }} · 文档 {{ user.knowledge_count }} · 任务 {{ user.task_count }}
                  </td>
                  <td class="px-4 py-3">
                    <button
                      @click="toggleAdmin(user)"
                      class="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      {{ user.roles.includes('admin') ? '取消管理员' : '设为管理员' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="space-y-5">
          <article class="rounded-lg border border-slate-200 bg-white p-4">
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-sm font-semibold text-slate-900">任务状态</h2>
              <Activity :size="16" class="text-slate-400" />
            </div>
            <div class="space-y-2">
              <div v-for="item in taskStatusItems" :key="item.key" class="flex items-center justify-between text-sm">
                <span class="text-slate-500">{{ item.label }}</span>
                <span class="font-semibold text-slate-900">{{ item.value }}</span>
              </div>
            </div>
          </article>

          <article class="rounded-lg border border-slate-200 bg-white p-4">
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-sm font-semibold text-slate-900">知识库状态</h2>
              <Database :size="16" class="text-slate-400" />
            </div>
            <div class="space-y-2">
              <div v-for="item in knowledgeStatusItems" :key="item.key" class="flex items-center justify-between text-sm">
                <span class="text-slate-500">{{ item.label }}</span>
                <span class="font-semibold text-slate-900">{{ item.value }}</span>
              </div>
            </div>
          </article>
        </section>
      </div>

      <section class="mt-5 rounded-lg border border-slate-200 bg-white">
        <div class="flex h-12 items-center justify-between border-b border-slate-200 px-4">
          <h2 class="text-sm font-semibold text-slate-900">最近后台任务</h2>
          <span class="text-xs text-slate-400">{{ tasks.length }} 条</span>
        </div>
        <div class="divide-y divide-slate-100">
          <article v-for="task in tasks" :key="task.id" class="grid gap-3 px-4 py-3 text-sm md:grid-cols-[1fr_120px_90px] md:items-center">
            <div class="min-w-0">
              <p class="truncate font-medium text-slate-900">{{ task.title }}</p>
              <p class="mt-1 text-xs text-slate-400">用户 {{ task.user_id }} · 助手 {{ task.agent_id ?? '-' }} · {{ task.created_at || '-' }}</p>
              <p v-if="task.error_msg" class="mt-1 line-clamp-2 text-xs text-red-600">{{ task.error_msg }}</p>
            </div>
            <div class="h-1.5 rounded bg-slate-200">
              <div class="h-1.5 rounded bg-blue-500" :style="{ width: `${task.progress || 0}%` }"></div>
            </div>
            <span :class="taskStatusClass(task.status)" class="w-fit rounded px-2 py-1 text-xs">
              {{ taskStatusText(task.status) }}
            </span>
          </article>
          <div v-if="!tasks.length && !loading" class="py-12 text-center text-sm text-slate-500">暂无后台任务。</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, Database, RefreshCcw } from 'lucide-vue-next'
import * as adminApi from '../api/admin'
import type { AdminOverview, AdminTask, AdminUser } from '../api/admin'
import { getErrorMessage } from '../utils/request'

const overview = ref<AdminOverview | null>(null)
const users = ref<AdminUser[]>([])
const tasks = ref<AdminTask[]>([])
const loading = ref(false)
const errorMsg = ref('')

const countLabels: Record<string, string> = {
  users: '用户',
  agents: '助手',
  skills: '能力',
  llm_configs: '模型连接',
  knowledge_docs: '文档',
  background_tasks: '后台任务',
}

const countItems = computed(() => Object.entries(countLabels).map(([key, label]) => ({
  key,
  label,
  value: overview.value?.counts?.[key] ?? 0,
})))

const taskStatusItems = computed(() => statusItems(overview.value?.task_status || {}))
const knowledgeStatusItems = computed(() => statusItems(overview.value?.knowledge_status || {}))

const statusItems = (data: Record<string, number>) => {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '处理中',
    finished: '已完成',
    failed: '失败',
    pending: '待处理',
    processing: '处理中',
    done: '已完成',
  }
  const keys = Object.keys(data)
  if (!keys.length) return [{ key: 'empty', label: '暂无数据', value: 0 }]
  return keys.map((key) => ({ key, label: labels[key] || key, value: data[key] }))
}

const taskStatusText = (s: string) => ({
  queued: '排队中',
  running: '处理中',
  finished: '已完成',
  failed: '失败',
}[s] || s)

const taskStatusClass = (s: string) => ({
  queued: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-50 text-blue-700',
  finished: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}[s] || 'bg-slate-100 text-slate-600')

const loadAll = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const [overviewData, userData, taskData] = await Promise.all([
      adminApi.getAdminOverview(),
      adminApi.listAdminUsers(),
      adminApi.listAdminTasks(50),
    ])
    overview.value = overviewData
    users.value = userData
    tasks.value = taskData
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '读取后台管理数据失败')
  } finally {
    loading.value = false
  }
}

const toggleAdmin = async (user: AdminUser) => {
  const nextRoles = user.roles.includes('admin')
    ? user.roles.filter((role) => role !== 'admin')
    : [...user.roles, 'admin']
  await adminApi.updateUserRoles(user.id, nextRoles)
  await loadAll()
}

onMounted(loadAll)
</script>
