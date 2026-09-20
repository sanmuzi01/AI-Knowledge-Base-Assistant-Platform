<template>
  <OnboardingWelcome
    v-if="store.phase === 'welcome'"
    :name="userStore.user?.name || '新朋友'"
    @start="store.start()"
    @skip="store.skipAll()"
  />

  <!-- 分步指引：桌面是左下角卡片，手机是右上角小胶囊，点开展开 -->
  <template v-if="store.phase === 'guide'">
    <button
      v-if="!expanded"
      type="button"
      :class="[
        'ui-glass-float !fixed z-40 inline-flex h-10 items-center gap-2 rounded-full pl-3 pr-4 text-[13px] font-medium',
        isDesktop ? ['bottom-5', leftClass] : 'right-3 top-[calc(3.5rem+env(safe-area-inset-top)+0.5rem)]',
      ]"
      @click="expanded = true"
    >
      <Sparkles :size="15" :stroke-width="1.9" class="relative text-[var(--accent)]" />
      <span class="relative">新手指引 {{ store.finishedCount }}/{{ steps.length }}</span>
    </button>

    <template v-else>
      <div v-if="!isDesktop" class="fixed inset-0 z-40 bg-black/25 backdrop-blur-[2px]" @click="expanded = false"></div>
      <aside
        :class="[
          'ui-glass-float !fixed w-[min(calc(100vw-1.5rem),21.5rem)] rounded-[22px] p-4',
          isDesktop ? 'z-40' : 'z-50',
          isDesktop ? ['bottom-5', leftClass] : 'right-3 top-[calc(3.5rem+env(safe-area-inset-top)+0.5rem)]',
        ]"
        aria-label="新手指引"
      >
        <div class="relative flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Sparkles :size="15" :stroke-width="1.9" class="text-[var(--accent)]" />
            <p class="text-[14px] font-semibold tracking-[-0.012em]">新手指引</p>
            <span class="text-[12px] tabular-nums text-slate-400">{{ store.finishedCount }} / {{ steps.length }}</span>
          </div>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-full text-slate-400 hover:bg-black/[.06] hover:text-slate-700"
            aria-label="收起"
            @click="expanded = false"
          >
            <ChevronDown :size="17" :stroke-width="2" />
          </button>
        </div>

        <div class="relative mt-3 flex gap-1.5">
          <span
            v-for="s in steps"
            :key="s.key"
            class="h-1 flex-1 rounded-full transition-colors duration-500"
            :class="stepState(s.key) === 'done' || stepState(s.key) === 'skipped' ? 'bg-[var(--accent)]' : 'bg-slate-200'"
          ></span>
        </div>

        <div v-if="store.justDone" class="ob-pop relative mt-3 flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-[13px] font-medium text-emerald-700">
          <Check :size="16" :stroke-width="2.4" />
          已完成「{{ stepTitle(store.justDone) }}」，马上带你去下一步
        </div>

        <ol class="relative mt-3 space-y-1">
          <li v-for="(s, i) in steps" :key="s.key">
            <div class="flex items-center gap-3 rounded-xl px-2 py-1.5" :class="stepState(s.key) === 'active' ? 'bg-[var(--accent-soft)]' : ''">
              <span
                class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
                :class="{
                  'ob-pop bg-emerald-500 text-white': stepState(s.key) === 'done',
                  'bg-slate-200 text-slate-400': stepState(s.key) === 'skipped',
                  'bg-[var(--accent)] text-white': stepState(s.key) === 'active',
                  'bg-slate-100 text-slate-400': stepState(s.key) === 'pending',
                }"
              >
                <Check v-if="stepState(s.key) === 'done'" :size="14" :stroke-width="3" />
                <Minus v-else-if="stepState(s.key) === 'skipped'" :size="13" :stroke-width="2.6" />
                <template v-else>{{ i + 1 }}</template>
              </span>
              <p
                class="min-w-0 flex-1 truncate text-[14px] tracking-[-0.008em]"
                :class="stepState(s.key) === 'active' ? 'font-semibold text-slate-900' : stepState(s.key) === 'pending' ? 'text-slate-500' : 'text-slate-400 line-through decoration-slate-300'"
              >
                {{ s.title }}<span v-if="s.optional" class="ml-1 text-[11px] font-normal text-slate-400 no-underline">可选</span>
              </p>
            </div>

            <div v-if="stepState(s.key) === 'active'" class="ob-rise pb-1 pl-11 pr-2 pt-1">
              <p class="text-[13px] leading-[1.6] text-slate-500">{{ s.desc }}</p>
              <div class="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  class="ui-primary inline-flex h-9 items-center gap-1.5 px-4 text-[13px] font-medium"
                  @click="go(s.key)"
                >
                  {{ s.cta }}
                  <ArrowRight :size="15" :stroke-width="2" />
                </button>
                <button v-if="s.optional" type="button" class="text-[13px] text-slate-400 hover:text-slate-700" @click="store.skipStep(s.key)">
                  跳过此步
                </button>
              </div>
            </div>
          </li>
        </ol>

        <div class="relative mt-2 flex justify-end border-t border-black/[.08] pt-2.5">
          <button type="button" class="text-[12px] text-slate-400 hover:text-slate-700" @click="store.skipAll()">跳过指引</button>
        </div>
      </aside>
    </template>
  </template>

  <!-- 全部完成 -->
  <div
    v-if="store.phase === 'finished'"
    class="fixed inset-0 z-[70] flex items-center justify-center bg-black/30 px-5 backdrop-blur-sm"
  >
    <section class="w-full max-w-[400px] rounded-[26px] bg-white p-8 text-center shadow-2xl">
      <span class="ob-pop mx-auto flex h-[72px] w-[72px] items-center justify-center rounded-full bg-emerald-500 text-white">
        <svg class="ob-check h-9 w-9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      </span>
      <h2 class="mt-6 text-[26px] font-semibold tracking-[-0.026em]">一切就绪</h2>
      <p class="mt-2.5 text-[14.5px] leading-[1.7] text-slate-500">
        你已经连接了模型、创建了助手并完成了第一次对话。接下来可以试试技能中心和 Agent 流水线，让助手更强。
      </p>
      <div class="mt-7 flex flex-col gap-2.5">
        <button type="button" class="ui-primary h-11 text-[15px] font-medium" @click="finish('/agents')">进入工作台</button>
        <button type="button" class="h-10 text-[14px] text-slate-500 hover:text-slate-900" @click="finish('/skills')">先去看看技能中心</button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check, ChevronDown, Minus, Sparkles } from 'lucide-vue-next'
import OnboardingWelcome from './OnboardingWelcome.vue'
import { ONBOARDING_STEPS, useOnboardingStore, type StepKey } from '../../stores/onboarding'
import { useUserStore } from '../../stores/user'
import { useAgentSessionStore } from '../../stores/agentSession'
import { listAgents } from '../../api/agent'

const store = useOnboardingStore()
const userStore = useUserStore()
const agentSession = useAgentSessionStore()
const route = useRoute()
const router = useRouter()
const steps = ONBOARDING_STEPS

const desktopQuery = window.matchMedia('(min-width: 768px)')
const isDesktop = ref(desktopQuery.matches)
const onQueryChange = (e: MediaQueryListEvent) => { isDesktop.value = e.matches }
desktopQuery.addEventListener('change', onQueryChange)

// 手机上默认收成小胶囊，桌面默认展开
const expanded = ref(isDesktop.value)

// 对话页的全局侧栏是 64px 图标栏，其余页面是 248px
const leftClass = computed(() => (/^\/agents\/\d+\/chat/.test(route.path) ? 'left-[5rem]' : 'left-[16.5rem]'))

type StepState = 'done' | 'skipped' | 'active' | 'pending'
const stepState = (key: StepKey): StepState => {
  if (store.doneMap[key]) return 'done'
  if (store.skipped.includes(key)) return 'skipped'
  return store.displayKey === key ? 'active' : 'pending'
}
const stepTitle = (key: StepKey) => steps.find((s) => s.key === key)?.title ?? ''

// ---- 跳转 ----
const resolveChatPath = async (): Promise<string> => {
  const id = agentSession.selectedAgent?.id || userStore.user?.selected_agent_id
  if (id) return `/agents/${id}/chat`
  try {
    const list = await listAgents()
    if (list.length) return `/agents/${list[0].id}/chat`
  } catch {
    /* 拿不到就回工作台 */
  }
  return '/agents'
}

async function go(key: StepKey) {
  if (key === 'model') {
    if (route.path !== '/llm-configs') await router.push('/llm-configs')
  } else if (key === 'agent') {
    await router.push({ path: '/agents', query: { create: '1' } })
  } else if (key === 'knowledge') {
    if (route.path !== '/knowledge-spaces') await router.push('/knowledge-spaces')
  } else {
    const path = await resolveChatPath()
    if (route.path !== path) await router.push(path)
  }
  if (!isDesktop.value) expanded.value = false
  highlight()
}

// ---- 目标高亮：给页面上"下一步该点的东西"加一圈脉冲 ----
const GUIDE_TARGET: Record<StepKey, string> = {
  model: 'api-key',
  agent: 'create-agent',
  knowledge: 'new-space',
  chat: 'composer',
}
let hlPoll: number | undefined
let hlOff: number | undefined
let hlEl: Element | null = null

function clearHighlight() {
  if (hlPoll) window.clearInterval(hlPoll)
  if (hlOff) window.clearTimeout(hlOff)
  hlEl?.classList.remove('guide-pulse')
  hlEl = null
}

function highlight() {
  clearHighlight()
  const key = store.displayKey
  if (!key || store.phase !== 'guide' || store.justDone) return
  const selector = `[data-guide="${GUIDE_TARGET[key]}"]`
  let tries = 0
  hlPoll = window.setInterval(() => {
    const el = document.querySelector(selector)
    if (el) {
      window.clearInterval(hlPoll)
      el.classList.add('guide-pulse')
      hlEl = el
      if (key === 'model') el.scrollIntoView({ block: 'center', behavior: 'smooth' })
      hlOff = window.setTimeout(() => el.classList.remove('guide-pulse'), 14000)
    } else if (++tries > 16) {
      window.clearInterval(hlPoll)
    }
  }, 300)
}

function finish(path: string) {
  store.closeFinished()
  router.push(path)
}

// ---- 联动 ----
watch(
  () => userStore.user,
  (u) => { if (u && !u.is_admin) void store.init(u.id) },
  { immediate: true },
)
watch(() => store.navRequest, (req) => { if (req) void go(req.key) })
watch(() => store.displayKey, () => highlight())
watch(() => route.fullPath, () => {
  if (store.phase !== 'guide') return
  void store.refresh()
  highlight()
})
watch(() => store.phase, (p) => {
  if (p === 'guide') expanded.value = isDesktop.value
  else clearHighlight()
})

const onFocus = () => { if (store.phase === 'guide') void store.refresh() }
onMounted(() => window.addEventListener('focus', onFocus))
onBeforeUnmount(() => {
  window.removeEventListener('focus', onFocus)
  desktopQuery.removeEventListener('change', onQueryChange)
  clearHighlight()
})
</script>
