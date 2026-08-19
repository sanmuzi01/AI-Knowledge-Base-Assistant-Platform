<template>
  <div class="h-screen min-w-0 bg-slate-100 text-slate-900">
    <div class="flex h-full min-w-0">
      <aside class="hidden w-56 shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col">
        <div class="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
          <span class="flex h-8 w-8 items-center justify-center rounded bg-slate-900 text-white">
            <Bot :size="17" />
          </span>
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold">Agent 平台</p>
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

          <div class="my-3 border-t border-slate-100"></div>

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

        <div class="border-t border-slate-200 p-2">
          <button
            @click="userStore.logout"
            class="flex h-10 w-full items-center gap-2 rounded px-3 text-sm text-slate-600 hover:bg-red-50 hover:text-red-600"
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
import { Bot, Brain, Bug, Database, KeyRound, Layers3, LogOut, MessageSquare, Settings, Zap } from 'lucide-vue-next'
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
    { label: 'Agent', path: '/agents', icon: Layers3, active: route.path.startsWith('/agents') },
    { label: 'Skill', path: '/skills', icon: Zap, active: route.path.startsWith('/skills') },
    { label: '模型 Key', path: '/llm-configs', icon: KeyRound, active: route.path.startsWith('/llm-configs') },
    { label: '系统设置', path: '/settings', icon: Settings, active: route.path.startsWith('/settings') },
  ]
})

const agentItems = computed(() => {
  const agentId = activeAgentId.value
  return [
    {
      label: '调试',
      path: agentId ? `/agents/${agentId}/debug` : route.fullPath,
      icon: Bug,
      active: route.path.includes('/debug'),
      disabled: !agentId,
    },
    {
      label: '聊天',
      path: agentId ? `/chat/${agentId}` : route.fullPath,
      icon: MessageSquare,
      active: route.path.startsWith('/chat'),
      disabled: !agentId,
    },
    {
      label: '记忆',
      path: agentId ? `/memory/${agentId}` : route.fullPath,
      icon: Brain,
      active: route.path.startsWith('/memory'),
      disabled: !agentId,
    },
    {
      label: '知识库',
      path: agentId ? `/knowledge/${agentId}` : route.fullPath,
      icon: Database,
      active: route.path.startsWith('/knowledge'),
      disabled: !agentId,
    },
  ]
})

const navClass = (active: boolean, disabled = false) => [
  'flex h-10 items-center gap-2 rounded px-3 text-sm transition-colors',
  active ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
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
