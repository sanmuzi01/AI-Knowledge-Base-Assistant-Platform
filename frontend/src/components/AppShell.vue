<template>
  <div class="app-starry h-screen min-w-0 text-slate-900">
    <div class="flex h-full min-w-0">
      <aside class="hidden w-60 shrink-0 border-r border-sky-200/70 bg-white/76 text-slate-900 shadow-2xl shadow-sky-900/10 backdrop-blur-xl md:flex md:flex-col">
        <div class="flex h-16 items-center gap-3 border-b border-sky-200/70 px-4">
          <span class="flex h-9 w-9 items-center justify-center rounded bg-sky-100 text-sky-700 ring-1 ring-sky-200">
            <Bot :size="17" />
          </span>
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold">AI 助手工作台</p>
            <p class="truncate text-xs text-slate-500">{{ userStore.user?.name || '当前用户' }}</p>
          </div>
        </div>

        <nav class="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          <RouterLink
            v-for="item in primaryItems"
            :key="item.path"
            :to="item.path"
            :class="navClass(item.active)"
          >
            <component :is="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </RouterLink>

          <div class="my-3 border-t border-sky-100"></div>
          <p class="px-3 pb-1 text-[11px] font-medium text-sky-600/70">当前助手</p>
          <RouterLink
            :to="agentSpace.disabled ? route.fullPath : agentSpace.path"
            :class="navClass(agentSpace.active, agentSpace.disabled)"
          >
            <MessageSquare :size="16" />
            <span class="truncate">{{ agentSpace.label }}</span>
          </RouterLink>
          <p v-if="agentSpace.disabled" class="px-3 pt-1 text-[11px] text-slate-400">先在工作台选一个助手</p>

          <div class="my-3 border-t border-sky-100"></div>
          <button
            type="button"
            @click="toggleMore"
            class="flex h-9 w-full items-center gap-2 rounded px-3 text-[11px] font-medium text-sky-600/70 hover:bg-sky-50"
          >
            <ChevronRight :size="13" :class="['transition-transform', moreOpen ? 'rotate-90' : '']" />
            <span>更多</span>
            <span v-if="!moreOpen && moreHasActive" class="ml-auto h-1.5 w-1.5 rounded-full bg-sky-400"></span>
          </button>
          <template v-if="moreOpen">
            <RouterLink
              v-for="item in moreItems"
              :key="item.path"
              :to="item.path"
              :class="navClass(item.active)"
            >
              <component :is="item.icon" :size="16" />
              <span>{{ item.label }}</span>
            </RouterLink>
          </template>
        </nav>

        <div class="border-t border-sky-100 p-2">
          <button
            @click="userStore.logout"
            class="flex h-10 w-full items-center gap-2 rounded px-3 text-sm text-slate-500 hover:bg-red-50 hover:text-red-600"
          >
            <LogOut :size="16" />
            <span>退出登录</span>
          </button>
        </div>
      </aside>

      <main class="min-w-0 flex-1 overflow-hidden">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Bot, ChevronRight, Layers3, LayoutGrid, Library, ListChecks, LogOut, MessageSquare, Settings, Zap } from 'lucide-vue-next'
import { useUserStore } from '../stores/user'
import * as agentApi from '../api/agent'
import type { AgentInfo } from '../api/agent'

const route = useRoute()
const userStore = useUserStore()
const selectedAgent = ref<AgentInfo | null>(null)

const routeAgentId = computed(() => {
  const value = route.params.agentId
  if (Array.isArray(value)) return Number(value[0])
  return value ? Number(value) : null
})

const activeAgentId = computed(() => {
  return routeAgentId.value || selectedAgent.value?.id || userStore.user?.selected_agent_id || null
})

const primaryItems = computed(() => [
  { label: '工作台', path: '/agents', icon: Layers3, active: route.path === '/agents' },
  { label: '知识库中心', path: '/knowledge-spaces', icon: Library, active: route.path.startsWith('/knowledge-spaces') },
])

const moreItems = computed(() => [
  { label: '小窗口与监控', path: '/widgets', icon: LayoutGrid, active: route.path.startsWith('/widgets') || route.path.startsWith('/web-monitor') },
  { label: '技能中心', path: '/skills', icon: Zap, active: route.path.startsWith('/skills') },
  { label: '任务中心', path: '/tasks', icon: ListChecks, active: route.path.startsWith('/tasks') },
  { label: '设置', path: '/settings', icon: Settings, active: route.path.startsWith('/settings') || route.path.startsWith('/llm-configs') },
])

const moreHasActive = computed(() => moreItems.value.some((i) => i.active))

const MORE_KEY = 'appshell.moreOpen'
const moreOpen = ref((() => {
  try { return localStorage.getItem(MORE_KEY) === '1' } catch { return false }
})())
const toggleMore = () => {
  moreOpen.value = !moreOpen.value
  try { localStorage.setItem(MORE_KEY, moreOpen.value ? '1' : '0') } catch { /* ignore */ }
}
// 当前在「更多」里的页面时自动展开，避免看不到高亮项
watch(moreHasActive, (v) => { if (v) moreOpen.value = true }, { immediate: true })

const agentSpace = computed(() => {
  const agentId = activeAgentId.value
  const inSpace = agentId != null && route.path.startsWith(`/agents/${agentId}/`)
  return {
    label: inSpace || agentId != null
      ? `助手空间${selectedAgent.value?.name ? ' · ' + selectedAgent.value.name : ''}`
      : '助手空间',
    path: agentId != null ? `/agents/${agentId}/chat` : route.fullPath,
    active: inSpace,
    disabled: agentId == null,
  }
})

const navClass = (active: boolean, disabled = false) => [
  'flex h-10 items-center gap-2 rounded px-3 text-sm transition-colors',
  active ? 'bg-sky-100 text-sky-800 ring-1 ring-sky-200' : 'text-slate-600 hover:bg-sky-50 hover:text-slate-900',
  disabled ? 'pointer-events-none cursor-not-allowed opacity-40' : '',
]

const loadSelectedAgent = async () => {
  try {
    await userStore.refreshMe()
    if (userStore.user?.is_admin || route.path.startsWith('/admin')) {
      selectedAgent.value = null
      return
    }
    selectedAgent.value = await agentApi.getSelectedAgent()
  } catch {
    selectedAgent.value = null
  }
}

onMounted(loadSelectedAgent)
watch(() => route.fullPath, loadSelectedAgent)
</script>
