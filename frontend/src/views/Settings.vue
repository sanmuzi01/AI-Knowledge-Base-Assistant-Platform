<template>
  <div class="h-screen overflow-y-auto bg-transparent p-6">
    <div class="mx-auto max-w-5xl">
      <header class="mb-4">
        <div class="mb-3 flex items-center justify-between">
          <div>
            <h1 class="text-base font-semibold text-slate-950">设置</h1>
            <p class="text-xs text-slate-500">连接 AI 服务、个性化画像，以及查看系统运行状态。</p>
          </div>
          <button
            @click="loadHealth"
            :disabled="loading"
            class="inline-flex items-center gap-2 rounded border border-sky-200 bg-white/80 px-3 py-2 text-sm text-slate-700 hover:bg-sky-50 disabled:text-slate-300"
          >
            <RefreshCcw :size="15" :class="loading ? 'animate-spin' : ''" />
            刷新
          </button>
        </div>
        <SectionTabs :tabs="[
          { label: '模型连接', path: '/llm-configs' },
          { label: '个性化与系统状态', path: '/settings' },
        ]" />
      </header>

      <section class="sci-panel mb-5 overflow-hidden rounded-lg p-5">
        <div class="mb-4 flex items-start justify-between gap-4">
          <div class="flex items-center gap-3">
            <span class="flex h-10 w-10 items-center justify-center rounded bg-sky-50 text-sky-700">
              <UserRound :size="18" />
            </span>
            <div>
              <h2 class="text-sm font-semibold text-slate-900">AI 个性化画像</h2>
              <p class="text-xs text-slate-500">这些信息会进入助手设定，用来调整回答深度、语气和例子。</p>
            </div>
          </div>
          <span class="hidden rounded border border-sky-100 bg-white/70 px-2 py-1 text-xs text-sky-700 md:inline-flex">
            私人配置
          </span>
        </div>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label class="space-y-1">
            <span class="text-xs font-medium text-slate-600">你的身份/职业</span>
            <input
              v-model="profileForm.occupation"
              class="sci-field h-10 w-full rounded px-3 text-sm outline-none"
              placeholder="例如：大学生、后端工程师、产品经理"
            />
          </label>
          <label class="space-y-1">
            <span class="text-xs font-medium text-slate-600">希望 AI 的人格</span>
            <select v-model="profileForm.persona" class="sci-field h-10 w-full rounded px-3 text-sm outline-none">
              <option value="professional">专业助理</option>
              <option value="coach">成长教练</option>
              <option value="teacher">耐心老师</option>
              <option value="partner">协作伙伴</option>
              <option value="analyst">分析顾问</option>
            </select>
          </label>
          <label class="space-y-1">
            <span class="text-xs font-medium text-slate-600">回答风格</span>
            <select v-model="profileForm.communication_style" class="sci-field h-10 w-full rounded px-3 text-sm outline-none">
              <option value="balanced">清晰稳重</option>
              <option value="concise">简洁直接</option>
              <option value="teacher">老师型讲解</option>
              <option value="friendly">朋友型交流</option>
              <option value="professional">专业顾问型</option>
            </select>
          </label>
          <label class="space-y-1">
            <span class="text-xs font-medium text-slate-600">技能背景</span>
            <input
              v-model="profileForm.skills"
              class="sci-field h-10 w-full rounded px-3 text-sm outline-none"
              placeholder="例如：会 Python，正在学习前端和部署"
            />
          </label>
          <label class="space-y-1 md:col-span-2">
            <span class="text-xs font-medium text-slate-600">长期偏好</span>
            <textarea
              v-model="profileForm.preferences"
              rows="3"
              class="sci-field w-full resize-none rounded px-3 py-2 text-sm outline-none"
              placeholder="例如：先给结论，再给步骤；代码要有中文注释；解释时多举实际项目例子"
            />
          </label>
          <label class="space-y-1 md:col-span-2">
            <span class="text-xs font-medium text-slate-600">其他补充</span>
            <textarea
              v-model="profileForm.extra_info"
              rows="3"
              class="sci-field w-full resize-none rounded px-3 py-2 text-sm outline-none"
              placeholder="例如：当前项目目标、常用技术栈、希望避免的回答方式"
            />
          </label>
        </div>

        <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p class="text-xs text-slate-400">
            {{ profileForm.updated_at ? `上次保存：${formatTime(profileForm.updated_at)}` : '保存后会自动用于后续对话' }}
          </p>
          <button
            @click="saveProfile"
            :disabled="savingProfile || profileLoading"
            class="sci-primary inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300 disabled:shadow-none"
          >
            <Save :size="15" />
            {{ savingProfile ? '保存中...' : '保存画像' }}
          </button>
        </div>
        <p v-if="profileError" class="mt-2 text-sm text-red-600">{{ profileError }}</p>
        <div class="mt-4 rounded border border-sky-100 bg-white/60 p-3">
          <div class="mb-2 flex items-center justify-between gap-3">
            <h3 class="text-xs font-semibold text-slate-700">AI 自动画像</h3>
            <span class="text-xs text-slate-400">
              {{ profileForm.last_inferred_at ? formatTime(profileForm.last_inferred_at) : '等待长期记忆触发' }}
            </span>
          </div>
          <p class="whitespace-pre-wrap text-xs leading-relaxed text-slate-500">
            {{ profileForm.auto_summary || '当你和助手完成足够多轮对话后，系统会从长期记忆中自动提炼稳定背景和偏好，显示在这里。' }}
          </p>
        </div>
      </section>

      <section class="sci-panel mb-5 rounded-lg p-5">
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
            class="sci-field h-10 rounded px-3 text-sm outline-none"
            placeholder="当前密码"
          />
          <input
            v-model="passwordForm.newPassword"
            type="password"
            class="sci-field h-10 rounded px-3 text-sm outline-none"
            placeholder="新密码，至少6位"
          />
          <button
            @click="changePassword"
            :disabled="changingPassword || !passwordForm.oldPassword || passwordForm.newPassword.length < 6"
            class="sci-primary rounded px-4 py-2 text-sm font-medium text-white disabled:bg-slate-300 disabled:shadow-none"
          >
            {{ changingPassword ? '修改中...' : '确认修改' }}
          </button>
        </div>
        <p v-if="passwordError" class="mt-2 text-sm text-red-600">{{ passwordError }}</p>
      </section>

      <section class="sci-panel mb-5 rounded-lg p-5" :class="health?.ok ? 'border-emerald-200' : 'border-amber-200'">
        <div class="flex items-center gap-3">
          <span :class="health?.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'" class="flex h-10 w-10 items-center justify-center rounded">
            <component :is="health?.ok ? CheckCircle2 : AlertTriangle" :size="20" />
          </span>
          <div>
            <h2 class="text-sm font-semibold text-slate-900">{{ health?.ok ? '服务运行正常' : '存在需要处理的问题' }}</h2>
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
          class="sci-panel rounded-lg p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-slate-900">{{ checkLabel(item.name) }}</h3>
              <p class="mt-1 break-all text-xs text-slate-500">{{ item.message }}</p>
            </div>
            <span :class="item.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'" class="shrink-0 rounded px-2 py-1 text-xs">
              {{ item.ok ? '正常' : '异常' }}
            </span>
          </div>
        </article>
      </div>

      <section class="sci-panel mt-5 rounded-lg p-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-900">缓存状态</h2>
          <span class="text-xs text-slate-400">来自 /health</span>
        </div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">模型配置缓存</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ health?.cache?.config?.size ?? 0 }} 条</p>
            <p class="mt-1 text-xs text-slate-400">
              {{ health?.cache?.config?.backend === 'redis' ? 'Redis' : '内存' }} · 已清理过期 {{ health?.cache?.config?.expired_removed ?? 0 }} 条
            </p>
          </article>
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">能力配置缓存</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ health?.cache?.skill?.size ?? 0 }} 条</p>
            <p class="mt-1 text-xs text-slate-400">
              {{ health?.cache?.skill?.backend === 'redis' ? 'Redis' : '内存' }} · 已清理过期 {{ health?.cache?.skill?.expired_removed ?? 0 }} 条
            </p>
          </article>
        </div>
      </section>

      <section class="sci-panel mt-5 rounded-lg p-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-900">访问管控</h2>
          <span class="text-xs text-slate-400">限流与并发</span>
        </div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">请求限流</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">
              {{ health?.limits?.rate?.backend === 'redis' ? 'Redis' : '内存' }}
            </p>
            <p class="mt-1 text-xs text-slate-400">本机窗口 {{ health?.limits?.rate?.memory_size ?? 0 }} 个</p>
          </article>
          <article class="rounded border border-slate-100 p-3">
            <p class="text-xs text-slate-500">并发控制</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">
              {{ health?.limits?.concurrency?.backend === 'redis' ? 'Redis' : '内存' }}
            </p>
            <p class="mt-1 text-xs text-slate-400">本机运行 {{ health?.limits?.concurrency?.memory_active ?? 0 }} 个</p>
          </article>
        </div>
      </section>

      <section class="sci-panel mt-5 rounded-lg p-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-900">后台任务</h2>
          <span
            class="rounded px-2 py-1 text-xs"
            :class="health?.tasks?.worker_required ? 'bg-indigo-50 text-indigo-700' : 'bg-emerald-50 text-emerald-700'"
          >
            {{ health?.tasks?.execution_mode || '-' }}
          </span>
        </div>
        <p class="text-xs text-slate-500">
          {{ health?.tasks?.worker_required ? '当前模式需要独立启动 Worker 处理队列任务' : '当前模式由 API 进程在响应后处理后台任务' }}
        </p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCcw, Save, UserRound } from 'lucide-vue-next'
import SectionTabs from '../components/SectionTabs.vue'
import * as systemApi from '../api/system'
import type { HealthStatus } from '../api/system'
import { defaultProfile, getUserProfile, saveUserProfile } from '../api/userProfile'
import type { UserProfile } from '../api/userProfile'
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
const profileForm = reactive<UserProfile>({ ...defaultProfile })
const profileLoading = ref(false)
const savingProfile = ref(false)
const profileError = ref('')

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

const loadProfile = async () => {
  profileLoading.value = true
  profileError.value = ''
  try {
    Object.assign(profileForm, defaultProfile, await getUserProfile())
  } catch (e: any) {
    profileError.value = getErrorMessage(e, '用户画像加载失败')
  } finally {
    profileLoading.value = false
  }
}

const saveProfile = async () => {
  savingProfile.value = true
  profileError.value = ''
  try {
    Object.assign(profileForm, await saveUserProfile(profileForm))
    toastSuccess('AI 个性化画像已保存')
  } catch (e: any) {
    profileError.value = getErrorMessage(e, '保存用户画像失败')
  } finally {
    savingProfile.value = false
  }
}

const formatTime = (value: string) => new Date(value).toLocaleString()

const checkLabel = (name: string) => ({
  database: '数据库',
  redis: '缓存服务',
  sms: '短信服务',
  static: '静态资源目录',
  knowledge_files: '资料文件目录',
  vector_db: '资料检索目录',
  skills: '能力包目录',
  secrets: '密钥配置',
  cors: '跨域访问',
  trusted_hosts: '访问域名',
}[name] || name)

onMounted(() => {
  loadHealth()
  loadProfile()
})
</script>
