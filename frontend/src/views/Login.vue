<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
    <main class="grid w-full max-w-5xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:grid-cols-[1fr_390px]">
      <section class="hidden bg-slate-950 p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div>
          <div class="mb-8 flex items-center gap-3">
            <span class="flex h-10 w-10 items-center justify-center rounded bg-white text-slate-950">
              <Bot :size="20" />
            </span>
            <div>
              <h1 class="text-lg font-semibold">Agent 平台</h1>
              <p class="text-xs text-slate-400">智能体、知识库、Skill 与任务管控</p>
            </div>
          </div>
          <h2 class="max-w-md text-3xl font-semibold leading-tight">统一管理你的 Agent 工作流</h2>
          <p class="mt-4 max-w-md text-sm leading-6 text-slate-300">
            登录后可以创建 Agent、配置模型 Key、导入 Skill、管理知识库，并通过后台管理查看系统状态。
          </p>
        </div>
        <div class="grid grid-cols-3 gap-3 text-sm">
          <div class="rounded border border-white/10 bg-white/5 p-3">
            <p class="text-lg font-semibold">RAG</p>
            <p class="mt-1 text-xs text-slate-400">知识检索</p>
          </div>
          <div class="rounded border border-white/10 bg-white/5 p-3">
            <p class="text-lg font-semibold">Skill</p>
            <p class="mt-1 text-xs text-slate-400">工具扩展</p>
          </div>
          <div class="rounded border border-white/10 bg-white/5 p-3">
            <p class="text-lg font-semibold">Admin</p>
            <p class="mt-1 text-xs text-slate-400">后台管控</p>
          </div>
        </div>
      </section>

      <section class="p-6 sm:p-8">
        <div class="mb-6 lg:hidden">
          <div class="mb-3 flex items-center gap-3">
            <span class="flex h-9 w-9 items-center justify-center rounded bg-slate-900 text-white">
              <Bot :size="18" />
            </span>
            <div>
              <h1 class="text-base font-semibold text-slate-900">Agent 平台</h1>
              <p class="text-xs text-slate-500">登录后开始使用</p>
            </div>
          </div>
        </div>

        <div class="mb-6">
          <h2 class="text-xl font-semibold text-slate-900">{{ isRegisterMode ? '创建账号' : '欢迎回来' }}</h2>
          <p class="mt-1 text-sm text-slate-500">{{ isRegisterMode ? '注册普通用户后即可创建自己的 Agent。' : '输入账号密码进入工作台。' }}</p>
        </div>

        <div class="mb-5 grid grid-cols-2 rounded border border-slate-200 bg-slate-50 p-1">
          <button
            @click="switchMode(false)"
            :class="!isRegisterMode ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
            class="h-9 rounded text-sm font-medium"
          >
            登录
          </button>
          <button
            @click="switchMode(true)"
            :class="isRegisterMode ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
            class="h-9 rounded text-sm font-medium"
          >
            注册
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">用户名</label>
            <input
              v-model="username"
              type="text"
              autocomplete="username"
              class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="请输入用户名"
              @keyup.enter="submit"
            />
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">密码</label>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="请输入密码"
              @keyup.enter="submit"
            />
          </div>

          <div v-if="isRegisterMode">
            <label class="mb-1 block text-sm font-medium text-slate-700">年龄</label>
            <input
              v-model.number="age"
              type="number"
              min="0"
              max="150"
              class="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="请输入年龄"
              @keyup.enter="submit"
            />
          </div>

          <p v-if="errorMsg" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ errorMsg }}</p>
          <p v-if="successMsg" class="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{{ successMsg }}</p>

          <button
            @click="submit"
            :disabled="loading"
            class="inline-flex h-10 w-full items-center justify-center rounded bg-blue-600 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-blue-300"
          >
            {{ loading ? '处理中...' : isRegisterMode ? '注册并登录' : '登录' }}
          </button>

        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bot } from 'lucide-vue-next'
import { useUserStore } from '../stores/user'
import { getErrorMessage } from '../utils/request'

const username = ref('')
const password = ref('')
const age = ref<number | null>(18)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const isRegisterMode = ref(false)
const router = useRouter()
const userStore = useUserStore()

const switchMode = (registerMode: boolean) => {
  isRegisterMode.value = registerMode
  errorMsg.value = ''
  successMsg.value = ''
}

const validate = () => {
  if (!username.value.trim() || !password.value) return '请输入用户名和密码'
  if (username.value.trim().length < 3 || username.value.trim().length > 20) return '用户名长度需要在 3-20 个字符之间'
  if (password.value.length < 6) return '密码至少需要 6 位'
  if (isRegisterMode.value && (age.value === null || age.value < 0 || age.value > 150)) return '年龄需要在 0-150 之间'
  return ''
}

const submit = async () => {
  const err = validate()
  if (err) {
    errorMsg.value = err
    return
  }
  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    if (isRegisterMode.value) {
      const result = await userStore.register(username.value.trim(), password.value, Number(age.value))
      if (result?.message && result.message !== '注册成功') {
        throw new Error(result.message)
      }
      successMsg.value = '注册成功，正在登录...'
    }
    await userStore.login(username.value.trim(), password.value)
    // 管理员跳 /admin，普通用户跳 /agents
    router.push(userStore.user?.is_admin ? '/admin' : '/agents')
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, isRegisterMode.value ? '注册失败' : '登录失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (userStore.token) router.push(userStore.user?.is_admin ? '/admin' : '/agents')
})
</script>
