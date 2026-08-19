<template>
  <div class="h-screen overflow-y-auto bg-slate-50 p-6">
    <div class="mx-auto max-w-5xl">
      <header class="mb-5 flex items-center justify-between">
        <div>
          <h1 class="text-base font-semibold text-slate-900">系统设置</h1>
          <p class="text-xs text-slate-500">账号安全、后端运行环境、关键配置和目录状态</p>
        </div>
        <button
          @click="loadHealth"
          :disabled="loading"
          class="inline-flex items-center gap-2 rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
        >
          <RefreshCcw :size="15" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
      </header>

      <section class="mb-5 rounded-lg border border-slate-200 bg-white p-5">
        <div class="mb-4 flex items-center gap-3">
          <span class="flex h-10 w-10 items-center justify-center rounded bg-slate-100 text-slate-600">
            <KeyRound :size="18" />
          </span>
          <div>
            <h2 class="text-sm font-semibold text-slate-900">修改密码</h2>
            <p class="text-xs text-slate-500">修改成功后需要重新登录</p>
          </div>
        </div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_auto]">
          <input
            v-model="passwordForm.oldPassword"
            type="password"
            class="h-10 rounded border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
            placeholder="当前密码"
          />
          <input
            v-model="passwordForm.newPassword"
            type="password"
            class="h-10 rounded border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
            placeholder="新密码，至少6位"
          />
          <button
            @click="changePassword"
            :disabled="changingPassword || !passwordForm.oldPassword || passwordForm.newPassword.length < 6"
            class="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-300"
          >
            {{ changingPassword ? '修改中...' : '确认修改' }}
          </button>
        </div>
        <p v-if="passwordError" class="mt-2 text-sm text-red-600">{{ passwordError }}</p>
      </section>

      <section class="mb-5 rounded-lg border bg-white p-5" :class="health?.ok ? 'border-emerald-200' : 'border-amber-200'">
        <div class="flex items-center gap-3">
          <span :class="health?.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'" class="flex h-10 w-10 items-center justify-center rounded">
            <component :is="health?.ok ? CheckCircle2 : AlertTriangle" :size="20" />
          </span>
          <div>
            <h2 class="text-sm font-semibold text-slate-900">{{ health?.ok ? '后端状态正常' : '存在需要处理的配置项' }}</h2>
            <p class="text-xs text-slate-500">{{ errorMsg || '健康检查来自 /health 接口' }}</p>
          </div>
        </div>
      </section>

      <div v-if="loading && !health" class="rounded-lg border border-slate-200 bg-white py-16 text-center text-sm text-slate-500">
        加载中...
      </div>

      <div v-else class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <article
          v-for="item in health?.checks || []"
          :key="item.name"
          class="rounded-lg border border-slate-200 bg-white p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-slate-900">{{ item.name }}</h3>
              <p class="mt-1 break-all text-xs text-slate-500">{{ item.message }}</p>
            </div>
            <span :class="item.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'" class="shrink-0 rounded px-2 py-1 text-xs">
              {{ item.ok ? '正常' : '异常' }}
            </span>
          </div>
        </article>
      </div>

      <section class="mt-5 rounded-lg border border-slate-200 bg-white p-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-900">缓存状态</h2>
          <span class="text-xs text-slate-400">来自 /health</span>
        </div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">模型配置缓存</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ health?.cache?.config?.size ?? 0 }} 条</p>
            <p class="mt-1 text-xs text-slate-400">已清理过期 {{ health?.cache?.config?.expired_removed ?? 0 }} 条</p>
          </article>
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">Skill 配置缓存</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ health?.cache?.skill?.size ?? 0 }} 条</p>
            <p class="mt-1 text-xs text-slate-400">已清理过期 {{ health?.cache?.skill?.expired_removed ?? 0 }} 条</p>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCcw } from 'lucide-vue-next'
import * as systemApi from '../api/system'
import type { HealthStatus } from '../api/system'
import { getErrorMessage } from '../utils/request'
import { useUserStore } from '../stores/user'
import { toastSuccess } from '../utils/toast'

const userStore = useUserStore()
const health = ref<HealthStatus | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const changingPassword = ref(false)
const passwordError = ref('')
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
})

const loadHealth = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    health.value = await systemApi.getHealth()
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '健康检查失败')
  } finally {
    loading.value = false
  }
}

const changePassword = async () => {
  if (!passwordForm.value.oldPassword || passwordForm.value.newPassword.length < 6) return
  changingPassword.value = true
  passwordError.value = ''
  try {
    await userStore.changePassword(passwordForm.value.oldPassword, passwordForm.value.newPassword)
    toastSuccess('密码已修改，请重新登录')
    userStore.logout()
  } catch (e: any) {
    passwordError.value = getErrorMessage(e, '修改密码失败')
  } finally {
    changingPassword.value = false
  }
}

onMounted(loadHealth)
</script>
