import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getUserDashboard, type UserDashboard } from '../api/userDashboard'

export type StepKey = 'model' | 'agent' | 'knowledge' | 'chat'

export interface OnboardingStep {
  key: StepKey
  title: string
  desc: string
  cta: string
  minutes: string
  optional?: boolean
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    key: 'model',
    title: '连接 AI 模型',
    desc: '选一个平台，粘贴访问密钥，助手才有“大脑”。调用地址系统会自动匹配。',
    cta: '去连接模型',
    minutes: '约 1 分钟',
  },
  {
    key: 'agent',
    title: '创建第一个助手',
    desc: '给助手起个名字，再选一个现成模板，一分钟就能建好。',
    cta: '新建助手',
    minutes: '约 1 分钟',
  },
  {
    key: 'knowledge',
    title: '添加资料',
    desc: '新建一个知识库空间并上传文档，助手就能基于你的资料回答，并标注来源。',
    cta: '去添加资料',
    minutes: '可选 · 约 2 分钟',
    optional: true,
  },
  {
    key: 'chat',
    title: '和助手聊一句',
    desc: '在输入框里问点什么，看看助手怎么回答。',
    cta: '开始对话',
    minutes: '约 30 秒',
  },
]

type Phase = 'off' | 'welcome' | 'guide' | 'finished'

interface Snapshot {
  llmConfigs: number
  chatModels: number
  agents: number
  knowledgeDocs: number
  conversations: number
  runs: number
  finishedRuns: number
}

interface Saved {
  phase: 'welcome' | 'guide' | 'done' | 'skipped'
  skipped: StepKey[]
}

const POLL_MS = 4000
const CELEBRATE_MS = 1400

const storageKey = (uid: number) => `onboarding:v1:${uid}`

const readSaved = (uid: number): Saved | null => {
  try {
    const raw = localStorage.getItem(storageKey(uid))
    return raw ? (JSON.parse(raw) as Saved) : null
  } catch {
    return null
  }
}

const toSnapshot = (d: UserDashboard): Snapshot => ({
  llmConfigs: d.counts.llm_configs,
  chatModels: d.counts.chat_models,
  agents: d.counts.agents,
  knowledgeDocs: d.counts.knowledge_docs,
  conversations: d.counts.conversations,
  runs: d.counts.runs,
  finishedRuns: d.status?.runs?.finished ?? d.recent_runs.filter((r) => r.status === 'finished').length,
})

const isDone = (key: StepKey, s: Snapshot | null): boolean => {
  if (!s) return false
  if (key === 'model') return s.chatModels > 0
  if (key === 'agent') return s.agents > 0
  if (key === 'knowledge') return s.knowledgeDocs > 0
  return s.finishedRuns > 0
}

// 只有"什么都还没有"的账号才算新用户；老用户不会被欢迎页打扰
const isBrandNew = (s: Snapshot) =>
  s.llmConfigs === 0 && s.agents === 0 && s.conversations === 0 && s.runs === 0 && s.knowledgeDocs === 0

export const useOnboardingStore = defineStore('onboarding', () => {
  const phase = ref<Phase>('off')
  const snap = ref<Snapshot | null>(null)
  const skipped = ref<StepKey[]>([])
  const displayKey = ref<StepKey | null>(null)
  const justDone = ref<StepKey | null>(null)
  const navRequest = ref<{ key: StepKey; nonce: number } | null>(null)
  const userId = ref<number | null>(null)
  let timer: number | undefined

  const doneMap = computed(() => {
    const map = {} as Record<StepKey, boolean>
    for (const s of ONBOARDING_STEPS) map[s.key] = isDone(s.key, snap.value)
    return map
  })
  const activeKey = computed<StepKey | null>(
    () => ONBOARDING_STEPS.find((s) => !doneMap.value[s.key] && !skipped.value.includes(s.key))?.key ?? null,
  )
  const finishedCount = computed(
    () => ONBOARDING_STEPS.filter((s) => doneMap.value[s.key] || skipped.value.includes(s.key)).length,
  )

  const persist = (p: Saved['phase']) => {
    if (userId.value == null) return
    try {
      localStorage.setItem(storageKey(userId.value), JSON.stringify({ phase: p, skipped: skipped.value }))
    } catch {
      /* 隐私模式下写不进去，本次会话内仍然有效 */
    }
  }

  const stopPolling = () => {
    if (timer) window.clearInterval(timer)
    timer = undefined
  }
  const startPolling = () => {
    stopPolling()
    timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, POLL_MS)
  }

  const fetchSnapshot = async () => {
    snap.value = toSnapshot(await getUserDashboard())
  }

  const complete = () => {
    stopPolling()
    phase.value = 'finished'
    displayKey.value = null
    persist('done')
  }

  const moveTo = (key: StepKey | null) => {
    if (phase.value !== 'guide') return
    justDone.value = null
    displayKey.value = key
    if (key) navRequest.value = { key, nonce: Date.now() }
    else complete()
  }

  async function refresh() {
    if (phase.value !== 'guide') return
    try {
      const prev = activeKey.value
      await fetchSnapshot()
      const now = activeKey.value
      if (now === prev) {
        if (!displayKey.value && now) displayKey.value = now
        return
      }
      // 上一步刚被真正做完：先亮一下"已完成"，再跳到下一步
      if (prev && doneMap.value[prev]) {
        justDone.value = prev
        displayKey.value = prev
        window.setTimeout(() => moveTo(now), CELEBRATE_MS)
      } else {
        moveTo(now)
      }
    } catch {
      /* 网络抖动，下个周期再试 */
    }
  }

  function reset() {
    stopPolling()
    phase.value = 'off'
    snap.value = null
    skipped.value = []
    displayKey.value = null
    justDone.value = null
    navRequest.value = null
  }

  async function init(uid: number) {
    if (userId.value === uid && phase.value !== 'off') return
    reset()
    userId.value = uid
    const saved = readSaved(uid)
    try {
      await fetchSnapshot()
    } catch {
      return
    }
    if (saved) {
      skipped.value = saved.skipped ?? []
      if (saved.phase === 'welcome') {
        phase.value = 'welcome'
      } else if (saved.phase === 'guide') {
        phase.value = 'guide'
        displayKey.value = activeKey.value
        if (!activeKey.value) complete()
        else startPolling()
      }
      return
    }
    if (snap.value && isBrandNew(snap.value)) {
      phase.value = 'welcome'
      persist('welcome')
    } else {
      persist('done')
    }
  }

  function start() {
    phase.value = 'guide'
    persist('guide')
    startPolling()
    moveTo(activeKey.value)
  }

  function skipAll() {
    stopPolling()
    phase.value = 'off'
    persist('skipped')
  }

  function skipStep(key: StepKey) {
    if (!skipped.value.includes(key)) skipped.value = [...skipped.value, key]
    persist('guide')
    moveTo(activeKey.value)
  }

  async function restart() {
    skipped.value = []
    try {
      await fetchSnapshot()
    } catch {
      /* 用上一次的快照 */
    }
    phase.value = 'guide'
    persist('guide')
    startPolling()
    moveTo(activeKey.value)
  }

  function closeFinished() {
    phase.value = 'off'
  }

  return {
    phase, snap, skipped, displayKey, justDone, navRequest, userId,
    doneMap, activeKey, finishedCount,
    init, refresh, start, skipAll, skipStep, restart, closeFinished, reset,
  }
})
