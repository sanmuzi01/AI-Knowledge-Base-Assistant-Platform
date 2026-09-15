<template>
  <div class="app-starry flex min-h-screen items-center justify-center px-4 py-8">
    <main class="grid w-full max-w-6xl overflow-hidden rounded-lg border border-sky-200/70 bg-white/72 shadow-2xl shadow-sky-900/12 backdrop-blur-xl lg:grid-cols-[minmax(0,1fr)_440px]">
      <section class="relative hidden min-h-[660px] overflow-hidden p-10 text-slate-900 lg:flex lg:flex-col lg:justify-between">
        <div class="pointer-events-none absolute inset-0 opacity-80">
          <span class="absolute left-12 top-28 h-1.5 w-1.5 rounded-full bg-sky-400 shadow-[0_0_18px_rgba(14,165,233,0.8)]"></span>
          <span class="absolute right-24 top-20 h-1 w-1 rounded-full bg-cyan-400 shadow-[0_0_16px_rgba(34,211,238,0.8)]"></span>
          <span class="absolute bottom-28 left-1/3 h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_18px_rgba(139,92,246,0.7)]"></span>
          <span class="sci-login-orbit"></span>
        </div>
        <div>
          <div class="mb-8 flex items-center gap-3">
            <span class="flex h-10 w-10 items-center justify-center rounded bg-sky-100 text-sky-700 ring-1 ring-sky-200">
              <Bot :size="20" />
            </span>
            <div>
              <h1 class="text-lg font-semibold">AI 助手工作台</h1>
              <p class="text-xs text-slate-500">连接模型、创建助手、添加资料、开始对话</p>
            </div>
          </div>
          <h2 class="max-w-lg text-4xl font-semibold leading-tight text-slate-950">一个账号，进入你的私人 AI 控制台</h2>
          <p class="mt-4 max-w-lg text-sm leading-6 text-slate-600">
            普通用户进入工作台配置模型、助手、资料和能力；管理员账号会自动进入后台管控页面。
          </p>
        </div>
        <div class="relative">
          <div class="mb-5 grid max-w-xl grid-cols-2 gap-3">
            <div
              v-for="item in capabilityCards"
              :key="item.title"
              class="rounded border border-sky-200/70 bg-white/62 p-4 backdrop-blur"
            >
              <component :is="item.icon" :size="18" class="text-sky-600" />
              <p class="mt-3 text-sm font-semibold text-slate-900">{{ item.title }}</p>
              <p class="mt-1 text-xs leading-5 text-slate-500">{{ item.desc }}</p>
            </div>
          </div>
          <div class="rounded-lg border border-sky-200/70 bg-white/68 p-4 backdrop-blur">
            <div class="flex items-center gap-2">
              <Sparkles :size="16" class="text-sky-600" />
              <span class="text-sm font-semibold text-slate-900">首次使用建议</span>
            </div>
            <div class="mt-3 grid grid-cols-4 gap-2 text-xs">
              <span
                v-for="step in onboardingSteps"
                :key="step"
                class="rounded border border-sky-100 bg-sky-50/70 px-2 py-2 text-center text-slate-600"
              >
                {{ step }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section class="bg-white/95 p-6 text-slate-900 backdrop-blur sm:p-8">
        <div class="mb-6 lg:hidden">
          <div class="mb-3 flex items-center gap-3">
            <span class="flex h-9 w-9 items-center justify-center rounded bg-sky-100 text-sky-700">
              <Bot :size="18" />
            </span>
            <div>
              <h1 class="text-base font-semibold text-slate-900">AI 助手工作台</h1>
              <p class="text-xs text-slate-500">登录后开始使用</p>
            </div>
          </div>
        </div>

        <div class="mb-6">
          <div class="mb-3 inline-flex items-center gap-2 rounded border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
            <ScanLine :size="13" />
            {{ isResetMode ? '找回密码' : isRegisterMode ? '普通用户注册' : '账号安全登录' }}
          </div>
          <h2 class="text-2xl font-semibold text-slate-950">{{ isResetMode ? '重置你的登录密码' : isRegisterMode ? '创建你的工作台账号' : '欢迎回来' }}</h2>
          <p class="mt-2 text-sm leading-6 text-slate-500">
            {{ isResetMode ? '用注册时的手机号接收验证码，验证通过后直接设置新密码。' : isRegisterMode ? '注册后可以创建自己的助手、资料库和能力配置。' : '系统会根据账号身份自动进入用户工作台或管理员后台。' }}
          </p>
        </div>

        <div v-if="!isResetMode" class="mb-5 grid grid-cols-2 rounded border border-slate-200 bg-slate-50 p-1">
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

        <div v-if="isResetMode" class="space-y-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">注册手机号</label>
            <div class="sci-field flex h-11 items-center gap-2 rounded px-3">
              <Phone :size="16" class="text-slate-400" />
              <input
                v-model="phone"
                type="tel"
                inputmode="numeric"
                autocomplete="tel"
                maxlength="11"
                class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="请输入注册时使用的手机号"
                @input="normalizePhoneInput"
                @keyup.enter="submit"
              />
            </div>
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">短信验证码</label>
            <div class="grid grid-cols-[1fr_118px] gap-2">
              <input
                v-model="smsCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                autocomplete="one-time-code"
                class="sci-field h-10 min-w-0 rounded px-3 text-sm outline-none"
                placeholder="6 位验证码"
                @keyup.enter="submit"
              />
              <button
                type="button"
                @click="sendSmsCode"
                :disabled="smsSending || smsCountdown > 0 || !canSendSms"
                class="inline-flex h-10 items-center justify-center rounded border border-blue-200 bg-blue-50 px-3 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
              >
                {{ smsButtonText }}
              </button>
            </div>
            <p v-if="smsHint" class="mt-1 text-xs text-slate-500">{{ smsHint }}</p>
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">新密码</label>
            <div class="sci-field flex h-11 items-center gap-2 rounded px-3">
              <LockKeyhole :size="16" class="text-slate-400" />
              <input
                v-model="resetNewPassword"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="至少 6 位"
                @keyup.enter="submit"
              />
              <button
                type="button"
                class="text-slate-400 hover:text-slate-700"
                :title="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <component :is="showPassword ? EyeOff : Eye" :size="16" />
              </button>
            </div>
          </div>

          <p v-if="errorMsg" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ errorMsg }}</p>
          <p v-if="successMsg" class="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{{ successMsg }}</p>

          <button
            @click="submit"
            :disabled="loading"
            class="sci-primary inline-flex h-11 w-full items-center justify-center gap-2 rounded text-sm font-medium text-white transition disabled:cursor-not-allowed disabled:bg-blue-300 disabled:shadow-none"
          >
            {{ loading ? '处理中...' : '重置密码' }}
            <ArrowRight v-if="!loading" :size="15" />
          </button>

          <button type="button" class="w-full text-center text-sm text-slate-500 hover:text-sky-700" @click="closeReset">
            返回登录
          </button>
        </div>

        <div v-else class="space-y-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">用户名</label>
            <div class="sci-field flex h-11 items-center gap-2 rounded px-3">
              <UserRound :size="16" class="text-slate-400" />
              <input
                v-model="username"
                type="text"
                autocomplete="username"
                class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="3-20 个字符"
                @keyup.enter="submit"
              />
            </div>
            <p v-if="usernameHint" class="mt-1 text-xs text-amber-600">{{ usernameHint }}</p>
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-slate-700">密码</label>
            <div class="sci-field flex h-11 items-center gap-2 rounded px-3">
              <LockKeyhole :size="16" class="text-slate-400" />
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
                class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="至少 6 位"
                @keyup.enter="submit"
              />
              <button
                type="button"
                class="text-slate-400 hover:text-slate-700"
                :title="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <component :is="showPassword ? EyeOff : Eye" :size="16" />
              </button>
            </div>
            <div v-if="isRegisterMode" class="mt-2">
              <div class="h-1.5 rounded bg-slate-100">
                <div class="h-1.5 rounded transition-all" :class="passwordStrengthClass" :style="{ width: `${passwordStrength.percent}%` }"></div>
              </div>
              <p class="mt-1 text-xs text-slate-500">密码强度：{{ passwordStrength.text }}</p>
            </div>
            <div v-if="!isRegisterMode" class="mt-1.5 text-right">
              <button type="button" class="text-xs text-sky-700 hover:text-sky-800" @click="openReset">忘记密码？</button>
            </div>
          </div>

          <div v-if="isRegisterMode">
            <label class="mb-1 block text-sm font-medium text-slate-700">年龄</label>
            <input
              v-model.number="age"
              type="number"
              min="0"
              max="150"
              class="sci-field h-10 w-full rounded px-3 text-sm outline-none"
              placeholder="请输入年龄"
              @keyup.enter="submit"
            />
          </div>

          <div v-if="isRegisterMode">
            <label class="mb-1 block text-sm font-medium text-slate-700">手机号</label>
            <div class="sci-field flex h-11 items-center gap-2 rounded px-3">
              <Phone :size="16" class="text-slate-400" />
              <input
                v-model="phone"
                type="tel"
                inputmode="numeric"
                autocomplete="tel"
                maxlength="11"
                class="h-full min-w-0 flex-1 bg-transparent text-sm outline-none"
                placeholder="请输入注册手机号"
                @input="normalizePhoneInput"
                @keyup.enter="submit"
              />
            </div>
          </div>

          <div v-if="isRegisterMode">
            <label class="mb-1 block text-sm font-medium text-slate-700">短信验证码</label>
            <div class="grid grid-cols-[1fr_118px] gap-2">
              <input
                v-model="smsCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                autocomplete="one-time-code"
                class="sci-field h-10 min-w-0 rounded px-3 text-sm outline-none"
                placeholder="6 位验证码"
                @keyup.enter="submit"
              />
              <button
                type="button"
                @click="sendSmsCode"
                :disabled="smsSending || smsCountdown > 0 || !canSendSms"
                class="inline-flex h-10 items-center justify-center rounded border border-blue-200 bg-blue-50 px-3 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
              >
                {{ smsButtonText }}
              </button>
            </div>
            <p v-if="smsHint" class="mt-1 text-xs text-slate-500">{{ smsHint }}</p>
          </div>

          <label
            v-if="isRegisterMode"
            class="flex cursor-pointer items-start gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 hover:border-sky-200 hover:bg-sky-50/60"
          >
            <input
              v-model="acceptedTerms"
              type="checkbox"
              class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span>
              我已阅读并同意
              <button type="button" class="font-medium text-blue-700 hover:text-blue-800" @click.prevent="showTerms = true">
                用户须知
              </button>
            </span>
          </label>

          <p v-if="errorMsg" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ errorMsg }}</p>
          <p v-if="successMsg" class="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{{ successMsg }}</p>

          <button
            @click="submit"
            :disabled="loading || (isRegisterMode && !acceptedTerms)"
            class="sci-primary inline-flex h-11 w-full items-center justify-center gap-2 rounded text-sm font-medium text-white transition disabled:cursor-not-allowed disabled:bg-blue-300 disabled:shadow-none"
          >
            {{ loading ? '处理中...' : isRegisterMode ? '注册并登录' : '进入系统' }}
            <ArrowRight v-if="!loading" :size="15" />
          </button>

          <div v-if="!isRegisterMode" class="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
            普通用户登录后进入工作台；管理员账号登录后会自动进入后台，普通用户无法进入管理员页面。
          </div>

        </div>
      </section>
    </main>

    <div v-if="showTerms" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
      <section class="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="text-base font-semibold text-slate-900">用户须知</h3>
            <p class="mt-1 text-sm text-slate-500">注册前请确认你理解以下使用规则。</p>
          </div>
          <button
            type="button"
            class="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            @click="showTerms = false"
          >
            <X :size="18" />
          </button>
        </div>
        <div class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
          <p>你需要妥善保管自己的账号、密码、模型密钥和上传资料，不要提交违法、侵权或包含敏感隐私的数据。</p>
          <p>平台会按功能需要处理你上传的资料、能力配置和对话内容，用于提供助手、检索和任务执行能力。</p>
          <p>管理员可基于安全、合规和资源保护需要，对异常账号、异常请求和高风险内容进行管控。</p>
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <button
            type="button"
            class="h-9 rounded border border-slate-200 px-4 text-sm text-slate-600 hover:bg-slate-50"
            @click="showTerms = false"
          >
            关闭
          </button>
          <button
            type="button"
            class="sci-primary h-9 rounded px-4 text-sm font-medium text-white"
            @click="acceptTerms"
          >
            同意并继续
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Bot, Brain, Database, Eye, EyeOff, LockKeyhole, Phone, ScanLine, ShieldCheck, Sparkles, UserRound, X, Zap } from 'lucide-vue-next'
import { useUserStore } from '../stores/user'
import { getErrorMessage } from '../utils/request'

const username = ref('')
const password = ref('')
const age = ref<number | null>(18)
const phone = ref('')
const smsCode = ref('')
const smsSending = ref(false)
const smsCountdown = ref(0)
const smsHint = ref('')
const acceptedTerms = ref(false)
const showTerms = ref(false)
const showPassword = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const isRegisterMode = ref(false)
const isResetMode = ref(false)
const resetNewPassword = ref('')
const router = useRouter()
const userStore = useUserStore()
let smsTimer: number | undefined

const capabilityCards = [
  { title: '私人助手', desc: '创建不同用途的 AI 助手', icon: Brain },
  { title: '知识空间', desc: '上传文档和网页资料', icon: Database },
  { title: '技能中心', desc: '安装或自定义工作流程', icon: Zap },
  { title: '后台管控', desc: '管理员查看用户、任务和日志', icon: ShieldCheck },
]
const onboardingSteps = ['连接模型', '创建助手', '添加资料', '开始对话']

const switchMode = (registerMode: boolean) => {
  isRegisterMode.value = registerMode
  errorMsg.value = ''
  successMsg.value = ''
}

const openReset = () => {
  isResetMode.value = true
  phone.value = ''
  smsCode.value = ''
  resetNewPassword.value = ''
  errorMsg.value = ''
  successMsg.value = ''
}

const closeReset = () => {
  isResetMode.value = false
  phone.value = ''
  smsCode.value = ''
  resetNewPassword.value = ''
  errorMsg.value = ''
  successMsg.value = ''
}

const normalizedPhone = computed(() => phone.value.replace(/\D/g, ''))
const canSendSms = computed(() => /^1[3-9]\d{9}$/.test(normalizedPhone.value))
const smsButtonText = computed(() => {
  if (smsSending.value) return '发送中...'
  if (smsCountdown.value > 0) return `${smsCountdown.value}s`
  return '获取验证码'
})
const usernameHint = computed(() => {
  const value = username.value.trim()
  if (!value) return ''
  if (value.length < 3) return '用户名至少 3 个字符'
  if (value.length > 20) return '用户名最多 20 个字符'
  return ''
})
const passwordStrength = computed(() => {
  const value = password.value
  let score = 0
  if (value.length >= 6) score += 1
  if (value.length >= 10) score += 1
  if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score += 1
  if (score <= 1) return { text: '较弱', percent: 28 }
  if (score === 2) return { text: '可用', percent: 56 }
  if (score === 3) return { text: '良好', percent: 78 }
  return { text: '较强', percent: 100 }
})
const passwordStrengthClass = computed(() => {
  if (passwordStrength.value.percent < 50) return 'bg-amber-400'
  if (passwordStrength.value.percent < 80) return 'bg-sky-500'
  return 'bg-emerald-500'
})

const startSmsCountdown = (seconds: number) => {
  smsCountdown.value = Math.max(1, seconds)
  if (smsTimer) window.clearInterval(smsTimer)
  smsTimer = window.setInterval(() => {
    smsCountdown.value -= 1
    if (smsCountdown.value <= 0 && smsTimer) {
      window.clearInterval(smsTimer)
      smsTimer = undefined
    }
  }, 1000)
}

const normalizePhoneInput = () => {
  phone.value = normalizedPhone.value.slice(0, 11)
}

const sendSmsCode = async () => {
  errorMsg.value = ''
  successMsg.value = ''
  smsHint.value = ''
  if (!canSendSms.value) {
    errorMsg.value = '请输入有效的手机号'
    return
  }
  smsSending.value = true
  try {
    const result = isResetMode.value
      ? await userStore.sendResetPasswordSmsCode(normalizedPhone.value)
      : await userStore.sendRegisterSmsCode(normalizedPhone.value)
    const retryAfter = Number(result?.retry_after || 60)
    startSmsCountdown(retryAfter)
    smsHint.value = result?.dev_code
      ? `本地开发验证码：${result.dev_code}`
      : '验证码已发送，请注意查收'
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '验证码发送失败')
  } finally {
    smsSending.value = false
  }
}

const acceptTerms = () => {
  acceptedTerms.value = true
  showTerms.value = false
}

const validate = () => {
  if (isResetMode.value) {
    if (!canSendSms.value) return '请输入有效的手机号'
    if (!/^\d{6}$/.test(smsCode.value.trim())) return '请输入 6 位短信验证码'
    if (resetNewPassword.value.length < 6) return '新密码至少需要 6 位'
    return ''
  }
  if (!username.value.trim() || !password.value) return '请输入用户名和密码'
  if (username.value.trim().length < 3 || username.value.trim().length > 20) return '用户名长度需要在 3-20 个字符之间'
  if (password.value.length < 6) return '密码至少需要 6 位'
  if (isRegisterMode.value) {
    if (age.value === null || age.value < 0 || age.value > 150) return '年龄需要在 0-150 之间'
    if (!canSendSms.value) return '请输入有效的手机号'
    if (!/^\d{6}$/.test(smsCode.value.trim())) return '请输入 6 位短信验证码'
    if (!acceptedTerms.value) return '请先阅读并同意用户须知'
  }
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
    if (isResetMode.value) {
      await userStore.resetPassword(normalizedPhone.value, smsCode.value.trim(), resetNewPassword.value)
      closeReset()
      successMsg.value = '密码已重置，请用新密码登录'
      return
    }
    if (isRegisterMode.value) {
      const result = await userStore.register(
        username.value.trim(),
        password.value,
        Number(age.value),
        normalizedPhone.value,
        smsCode.value.trim(),
        acceptedTerms.value,
      )
      if (result?.message && result.message !== '注册成功') {
        throw new Error(result.message)
      }
      successMsg.value = '注册成功，正在登录...'
    }
    await userStore.login(username.value.trim(), password.value)
    // 管理员跳 /admin，普通用户跳 /agents
    router.push(userStore.user?.is_admin ? '/admin' : '/agents')
  } catch (e: any) {
    const fallback = isResetMode.value ? '重置密码失败' : isRegisterMode.value ? '注册失败' : '登录失败'
    errorMsg.value = getErrorMessage(e, fallback)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (userStore.token) router.push(userStore.user?.is_admin ? '/admin' : '/agents')
})

onUnmounted(() => {
  if (smsTimer) window.clearInterval(smsTimer)
})
</script>
