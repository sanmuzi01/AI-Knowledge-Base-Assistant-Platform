<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <!-- 顶栏 -->
    <header class="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <button @click="$router.push('/agents')" class="text-sm text-gray-500 hover:text-gray-700">
          ← 返回
        </button>
        <span class="text-gray-300">|</span>
        <h1 class="text-lg font-semibold text-gray-800">后台任务中心</h1>
        <span v-if="isAdmin && showAll" class="text-xs px-2 py-0.5 bg-red-50 text-red-600 rounded">
          管理员·全局
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="isAdmin"
          @click="toggleScope"
          class="px-3 py-1.5 text-xs border rounded-lg transition-colors"
          :class="showAll
            ? 'border-red-200 text-red-600 bg-red-50'
            : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
        >
          {{ showAll ? '看全局任务' : '看我的任务' }}
        </button>
        <label class="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
          <input type="checkbox" v-model="autoRefresh" class="rounded" />
          自动刷新
        </label>
        <button
          @click="reload()"
          class="px-3 py-1.5 text-sm text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors flex items-center gap-1"
        >
          <RefreshCw :size="14" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
      </div>
    </header>

    <!-- 筛选栏 -->
    <div class="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">状态</span>
        <div class="flex gap-1">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            @click="filterStatus = opt.value"
            :class="[
              'px-2.5 py-1 text-xs rounded-full transition-colors',
              filterStatus === opt.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            ]"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">类型</span>
        <select
          v-model="filterType"
          class="text-xs border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">全部</option>
          <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div class="ml-auto text-xs text-gray-400">
        共 {{ tasks.length }} 条
      </div>
    </div>

    <!-- 任务列表 -->
    <main class="flex-1 overflow-y-auto p-6">
      <div class="max-w-5xl mx-auto">
        <div v-if="!loading && tasks.length === 0" class="text-center py-16 text-gray-400">
          暂无任务
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="task in tasks"
            :key="task.id"
            class="bg-white border rounded-xl p-4 hover:shadow-sm transition-shadow"
            :class="statusBorder(task.status)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <!-- 标题行 -->
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium text-gray-800 truncate">{{ task.title }}</span>
                  <span
                    class="text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1"
                    :class="statusBadge(task.status)"
                  >
                    <component :is="statusIcon(task.status)" :size="11" />
                    {{ statusLabel(task.status) }}
                  </span>
                  <span class="text-xs text-gray-400 font-mono">#{{ task.id }}</span>
                  <span v-if="task.retry_count > 0" class="text-xs px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded">
                    重试 {{ task.retry_count }} 次
                  </span>
                </div>
                <!-- 元数据行 -->
                <div class="text-xs text-gray-500 flex items-center gap-3 flex-wrap">
                  <span class="font-mono">{{ task.task_type }}</span>
                  <span v-if="showAll">用户 #{{ task.user_id }}</span>
                  <span v-if="task.agent_id">Agent #{{ task.agent_id }}</span>
                  <span v-if="task.target_type">→ {{ task.target_type }} #{{ task.target_id }}</span>
                  <span>创建: {{ task.created_at }}</span>
                  <span v-if="task.finished_at">完成: {{ task.finished_at }}</span>
                </div>
                <!-- 进度条（running 时显示） -->
                <div v-if="task.status === 'running' || task.progress > 0" class="mt-2">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        class="h-full bg-blue-500 rounded-full transition-all duration-300"
                        :style="{ width: task.progress + '%' }"
                      ></div>
                    </div>
                    <span class="text-xs text-gray-500 w-9 text-right">{{ task.progress }}%</span>
                  </div>
                </div>
                <!-- 错误信息（failed 时显示） -->
                <div v-if="task.status === 'failed' && task.error_msg" class="mt-2">
                  <div class="text-xs bg-red-50 border border-red-100 rounded p-2 text-red-700 font-mono whitespace-pre-wrap break-all">
                    {{ task.error_msg }}
                  </div>
                </div>
                <!-- 结果（finished 时显示，可折叠） -->
                <details v-if="task.status === 'finished' && task.result" class="mt-2">
                  <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-700">查看结果</summary>
                  <pre class="text-xs bg-gray-50 rounded p-2 mt-1 overflow-x-auto text-gray-700">{{ JSON.stringify(task.result, null, 2) }}</pre>
                </details>
              </div>
              <!-- 操作按钮 -->
              <div class="flex flex-col gap-1 shrink-0">
                <button
                  v-if="canRetry(task)"
                  @click="handleRetry(task)"
                  :disabled="actingId === task.id"
                  class="px-2.5 py-1 text-xs border border-amber-200 text-amber-700 rounded hover:bg-amber-50 transition-colors flex items-center gap-1 disabled:opacity-50"
                >
                  <RotateCcw :size="12" />
                  重试
                </button>
                <button
                  v-if="canCancel(task)"
                  @click="handleCancel(task)"
                  :disabled="actingId === task.id"
                  class="px-2.5 py-1 text-xs border border-gray-300 text-gray-600 rounded hover:bg-gray-50 transition-colors flex items-center gap-1 disabled:opacity-50"
                >
                  <X :size="12" />
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { RefreshCw, RotateCcw, X, Clock, Loader, CheckCircle2, AlertCircle, Ban } from 'lucide-vue-next'
import { useUserStore } from '../stores/user'
import * as taskApi from '../api/task'
import type { Task, TaskStatus } from '../api/task'

const userStore = useUserStore()
const isAdmin = computed(() => !!userStore.user?.is_admin)

// ===== 数据 =====
const tasks = ref<Task[]>([])
const loading = ref(false)
const actingId = ref<number | null>(null)

// ===== 筛选 =====
const filterStatus = ref<TaskStatus | ''>('')
const filterType = ref('')
const statusOptions = [
  { value: '' as const, label: '全部' },
  { value: 'queued' as const, label: '排队' },
  { value: 'running' as const, label: '执行中' },
  { value: 'finished' as const, label: '成功' },
  { value: 'failed' as const, label: '失败' },
  { value: 'cancelled' as const, label: '已取消' },
]
const typeOptions = computed(() => {
  const set = new Set(tasks.value.map(t => t.task_type))
  return [...set].sort()
})

// ===== 管理员模式 =====
const showAll = ref(false)
const toggleScope = () => {
  showAll.value = !showAll.value
  reload()
}

// ===== 自动刷新 =====
const autoRefresh = ref(true)
let timer: number | null = null
const hasRunning = computed(() => tasks.value.some(t => t.status === 'queued' || t.status === 'running'))

watch([hasRunning, autoRefresh], ([running, ar]) => {
  // 有排队/执行中 且 开启自动刷新 → 5 秒轮询
  if (running && ar && !timer) {
    timer = window.setInterval(() => reload(true), 5000)
  } else if ((!running || !ar) && timer) {
    clearInterval(timer)
    timer = null
  }
}, { immediate: true })

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// ===== 加载 =====
const reload = async (silent = false) => {
  loading.value = !silent
  try {
    const params = {
      status: filterStatus.value || undefined,
      task_type: filterType.value || undefined,
      limit: 100,
    }
    if (showAll.value && isAdmin.value) {
      tasks.value = await taskApi.listAllTasks(params)
    } else {
      tasks.value = await taskApi.listTasks(params)
    }
  } catch (e) {
    if (!silent) console.error('加载任务失败:', e)
  } finally {
    loading.value = false
  }
}

watch([filterStatus, filterType], () => reload())

// ===== 操作 =====
const canRetry = (t: Task) => t.status === 'failed' || t.status === 'cancelled'
const canCancel = (t: Task) => t.status === 'queued'

const handleRetry = async (t: Task) => {
  if (!confirm(`确认重试任务「${t.title}」？将创建新任务并重新执行。`)) return
  actingId.value = t.id
  try {
    await taskApi.retryTask(t.id)
    await reload(true)
  } catch (e: any) {
    alert(e?.response?.data?.detail || '重试失败')
  } finally {
    actingId.value = null
  }
}

const handleCancel = async (t: Task) => {
  if (!confirm(`确认取消任务「${t.title}」？`)) return
  actingId.value = t.id
  try {
    await taskApi.cancelTask(t.id)
    await reload(true)
  } catch (e: any) {
    alert(e?.response?.data?.detail || '取消失败')
  } finally {
    actingId.value = null
  }
}

// ===== 状态辅助 =====
const statusLabel = (s: TaskStatus) => ({
  queued: '排队中', running: '执行中', finished: '成功', failed: '失败', cancelled: '已取消',
}[s] || s)

const statusIcon = (s: TaskStatus) => ({
  queued: Clock, running: Loader, finished: CheckCircle2, failed: AlertCircle, cancelled: Ban,
}[s] || Clock)

const statusBadge = (s: TaskStatus) => ({
  queued: 'bg-gray-100 text-gray-600',
  running: 'bg-blue-50 text-blue-600',
  finished: 'bg-green-50 text-green-600',
  failed: 'bg-red-50 text-red-600',
  cancelled: 'bg-amber-50 text-amber-600',
}[s] || 'bg-gray-100 text-gray-600')

const statusBorder = (s: TaskStatus) => ({
  queued: 'border-gray-200',
  running: 'border-blue-200',
  finished: 'border-green-200',
  failed: 'border-red-200',
  cancelled: 'border-amber-200',
}[s] || 'border-gray-200')

onMounted(() => reload())
</script>
