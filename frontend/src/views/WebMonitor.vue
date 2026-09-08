<template>
  <div class="flex h-screen flex-col bg-transparent text-slate-950">
    <header class="border-b border-sky-200/70 bg-white/80 px-5 py-4 shadow-sm backdrop-blur-xl lg:px-8">
      <div class="mx-auto flex max-w-6xl flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex items-start gap-3">
          <button
            @click="router.push('/agents')"
            class="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
            title="返回工作台"
          >
            <ArrowLeft :size="16" />
          </button>
          <div>
            <h1 class="text-xl font-semibold">网页监控</h1>
            <p class="mt-1 text-sm text-slate-500">添加网页、公告或实时数据地址，手动检查变化；后续可接入定时任务和通知。</p>
          </div>
        </div>
        <button
          @click="showCreate = true"
          class="sci-primary inline-flex h-10 items-center gap-2 rounded px-4 text-sm font-medium text-white"
        >
          <Plus :size="16" />
          添加监控
        </button>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto px-5 py-6 lg:px-8">
      <div class="mx-auto max-w-6xl">
        <div v-if="loading" class="py-16 text-center text-sm text-slate-500">加载中...</div>
        <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {{ loadError }}
        </div>
        <div v-else-if="monitors.length === 0" class="rounded-lg border border-dashed border-sky-200 bg-white/70 py-14 text-center">
          <Globe2 :size="34" class="mx-auto text-sky-400" />
          <p class="mt-3 text-sm font-semibold text-slate-900">还没有网页监控</p>
          <p class="mt-1 text-sm text-slate-500">先添加一个 URL，系统会保存检查状态和最近变化。</p>
        </div>

        <div v-else class="grid gap-4 lg:grid-cols-2">
          <article v-for="item in monitors" :key="item.id" class="sci-panel rounded-lg p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 class="truncate text-sm font-semibold text-slate-950">{{ item.name }}</h2>
                <p class="mt-1 truncate text-xs text-slate-500">{{ item.url }}</p>
              </div>
              <span class="shrink-0 rounded px-2 py-1 text-xs" :class="statusClass(item.last_status)">
                {{ statusText(item.last_status) }}
              </span>
            </div>
            <div class="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-500">
              <span class="rounded border border-slate-100 bg-white/70 px-2 py-2">频率：{{ item.interval_minutes }} 分钟</span>
              <span class="rounded border border-slate-100 bg-white/70 px-2 py-2">最近：{{ item.last_checked_at || '未检查' }}</span>
            </div>
            <p v-if="item.last_error" class="mt-3 rounded border border-red-100 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
              {{ item.last_error }}
            </p>
            <p v-else-if="item.last_excerpt" class="mt-3 line-clamp-3 text-xs leading-5 text-slate-500">
              {{ item.last_excerpt }}
            </p>
            <div class="mt-4 flex justify-end gap-2 border-t border-slate-100 pt-3">
              <button
                @click="toggleActive(item)"
                class="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                {{ item.is_active ? '暂停' : '启用' }}
              </button>
              <button
                @click="check(item)"
                :disabled="checkingId === item.id"
                class="rounded border border-sky-200 bg-white px-3 py-1.5 text-xs text-sky-700 hover:bg-sky-50 disabled:text-slate-300"
              >
                {{ checkingId === item.id ? '检查中' : '立即检查' }}
              </button>
              <button
                @click="remove(item)"
                class="inline-flex h-8 w-8 items-center justify-center rounded border border-red-100 bg-white text-red-500 hover:bg-red-50"
                title="删除"
              >
                <Trash2 :size="14" />
              </button>
            </div>
          </article>
        </div>
      </div>
    </main>

    <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 backdrop-blur-sm">
      <section class="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-5 shadow-2xl">
        <div class="flex items-center justify-between">
          <h2 class="text-base font-semibold">添加网页监控</h2>
          <button @click="showCreate = false" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            <X :size="16" />
          </button>
        </div>
        <div class="mt-4 space-y-3">
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-600">名称</span>
            <input v-model="form.name" class="sci-field h-10 w-full rounded px-3 text-sm outline-none" placeholder="例如 招聘页面、价格页、公告页" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-600">网页地址</span>
            <input v-model="form.url" class="sci-field h-10 w-full rounded px-3 text-sm outline-none" placeholder="https://example.com/page" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-600">检查频率</span>
            <select v-model.number="form.interval_minutes" class="sci-field h-10 w-full rounded px-3 text-sm outline-none">
              <option :value="5">每 5 分钟</option>
              <option :value="15">每 15 分钟</option>
              <option :value="30">每 30 分钟</option>
              <option :value="60">每 1 小时</option>
              <option :value="360">每 6 小时</option>
            </select>
          </label>
          <p v-if="formError" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ formError }}</p>
        </div>
        <div class="mt-5 flex justify-end gap-2 border-t border-slate-100 pt-4">
          <button @click="showCreate = false" class="rounded border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">取消</button>
          <button @click="submit" :disabled="submitting || !form.url.trim()" class="sci-primary rounded px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300">
            {{ submitting ? '保存中...' : '保存' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Globe2, Plus, Trash2, X } from 'lucide-vue-next'
import * as webMonitorApi from '../api/webMonitor'
import type { WebMonitor } from '../api/webMonitor'
import { getErrorMessage } from '../utils/request'
import { toastError, toastSuccess } from '../utils/toast'

const router = useRouter()
const monitors = ref<WebMonitor[]>([])
const loading = ref(false)
const loadError = ref('')
const showCreate = ref(false)
const submitting = ref(false)
const checkingId = ref<number | null>(null)
const formError = ref('')
const form = reactive({
  name: '',
  url: '',
  interval_minutes: 30,
})

const reload = async () => {
  loading.value = true
  loadError.value = ''
  try {
    monitors.value = await webMonitorApi.listWebMonitors()
  } catch (e: any) {
    loadError.value = getErrorMessage(e, '加载网页监控失败')
  } finally {
    loading.value = false
  }
}

const submit = async () => {
  submitting.value = true
  formError.value = ''
  try {
    await webMonitorApi.createWebMonitor({ ...form })
    form.name = ''
    form.url = ''
    form.interval_minutes = 30
    showCreate.value = false
    toastSuccess('网页监控已添加')
    await reload()
  } catch (e: any) {
    formError.value = getErrorMessage(e, '添加网页监控失败')
  } finally {
    submitting.value = false
  }
}

const check = async (item: WebMonitor) => {
  checkingId.value = item.id
  try {
    const result = await webMonitorApi.checkWebMonitor(item.id)
    const index = monitors.value.findIndex((monitor) => monitor.id === item.id)
    if (index >= 0) monitors.value[index] = result
    toastSuccess(result.changed ? '检测到网页变化' : '网页暂无变化')
  } catch (e: any) {
    toastError(getErrorMessage(e, '检查网页失败'))
  } finally {
    checkingId.value = null
  }
}

const toggleActive = async (item: WebMonitor) => {
  try {
    const result = await webMonitorApi.updateWebMonitor(item.id, { is_active: !item.is_active })
    const index = monitors.value.findIndex((monitor) => monitor.id === item.id)
    if (index >= 0) monitors.value[index] = result
  } catch (e: any) {
    toastError(getErrorMessage(e, '更新网页监控失败'))
  }
}

const remove = async (item: WebMonitor) => {
  if (!confirm(`确认删除「${item.name}」？`)) return
  try {
    await webMonitorApi.deleteWebMonitor(item.id)
    monitors.value = monitors.value.filter((monitor) => monitor.id !== item.id)
  } catch (e: any) {
    toastError(getErrorMessage(e, '删除网页监控失败'))
  }
}

const statusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待检查',
    normal: '正常',
    changed: '有变化',
    failed: '失败',
  }
  return map[status] || status || '未知'
}

const statusClass = (status: string) => {
  if (status === 'changed') return 'bg-amber-50 text-amber-700'
  if (status === 'failed') return 'bg-red-50 text-red-700'
  if (status === 'normal') return 'bg-emerald-50 text-emerald-700'
  return 'bg-slate-100 text-slate-500'
}

onMounted(reload)
</script>
