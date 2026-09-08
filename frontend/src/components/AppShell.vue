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
          <p class="px-3 pb-1 text-[11px] font-medium text-sky-600/70">开始使用</p>
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
          <p class="px-3 pb-1 text-[11px] font-medium text-sky-600/70">当前使用</p>

          <RouterLink
            v-for="item in agentItems"
            :key="item.label"
            :to="item.disabled ? route.fullPath : item.path"
            :class="navClass(item.active, item.disabled)"
          >
            <component :is="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </RouterLink>
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
import { Bot, Brain, Bug, Database, Globe2, KeyRound, Layers3, LogOut, MessageSquare, Settings, Zap } from 'lucide-vue-next'
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

const primaryItems = computed(() => {
  return [
    { label: '工作台', path: '/agents', icon: Layers3, active: route.path.startsWith('/agents') },
    { label: '连接模型', path: '/llm-configs', icon: KeyRound, active: route.path.startsWith('/llm-configs') },
    { label: '技能中心', path: '/skills', icon: Zap, active: route.path.startsWith('/skills') },
    { label: '网页监控', path: '/web-monitor', icon: Globe2, active: route.path.startsWith('/web-monitor') },
    { label: '系统状态', path: '/settings', icon: Settings, active: route.path.startsWith('/settings') },
  ]
})

const agentItems = computed(() => {
  const agentId = activeAgentId.value
  return [
    {
      label: '聊天',
      path: agentId ? `/chat/${agentId}` : route.fullPath,
      icon: MessageSquare,
      active: route.path.startsWith('/chat'),
      disabled: !agentId,
    },
    {
      label: '个人资料',
      path: agentId ? `/knowledge/${agentId}` : route.fullPath,
      icon: Database,
      active: route.path.startsWith('/knowledge'),
      disabled: !agentId,
    },
    {
      label: '长期记忆',
      path: agentId ? `/memory/${agentId}` : route.fullPath,
      icon: Brain,
      active: route.path.startsWith('/memory'),
      disabled: !agentId,
    },
    {
      label: '运行检查',
      path: agentId ? `/agents/${agentId}/debug` : route.fullPath,
      icon: Bug,
      active: route.path.includes('/debug'),
      disabled: !agentId,
    },
  ]
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
