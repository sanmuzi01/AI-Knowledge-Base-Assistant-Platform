<template>
  <div class="h-screen min-w-0 bg-slate-100 text-slate-900">
    <div class="flex h-full min-w-0">
      <aside class="hidden w-56 shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col">
      <div class="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
        <span class="flex h-8 w-8 items-center justify-center rounded bg-slate-900 text-white">
          <ShieldCheck :size="17" />
        </span>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-slate-900">管理后台</p>
          <p class="truncate text-xs text-slate-500">{{ userStore.user?.name || '管理员' }}</p>
        </div>
      </div>

      <nav class="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="navClass($route.path === item.path || (item.path === '/admin/overview' && $route.path === '/admin'))"
        >
          <component :is="item.icon" :size="16" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="border-t border-slate-200 p-2">
        <button
          @click="logout"
          class="flex h-10 w-full items-center gap-2 rounded px-3 text-sm text-slate-600 hover:bg-red-50 hover:text-red-600"
        >
          <LogOut :size="16" />
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <!-- 主体 -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div class="flex items-center gap-3">
          <h1 class="text-base font-semibold text-slate-900">{{ currentTitle }}</h1>
        </div>
        <div class="flex items-center gap-3 text-sm text-slate-500">
          <span class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">管理员</span>
          <span>{{ userStore.user?.name }}</span>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto">
        <RouterView />
      </main>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink, RouterView } from 'vue-router'
import {
  LayoutDashboard, Users, ListChecks, BarChart3, ScrollText,
  Stethoscope, ShieldCheck, LogOut,
} from 'lucide-vue-next'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const userStore = useUserStore()

const navItems = [
  { path: '/admin/overview', label: '系统概览', icon: LayoutDashboard },
  { path: '/admin/users', label: '用户管理', icon: Users },
  { path: '/admin/tasks', label: '后台任务', icon: ListChecks },
  { path: '/admin/usage', label: '使用情况', icon: BarChart3 },
  { path: '/admin/logs', label: '操作日志', icon: ScrollText },
  { path: '/admin/diagnose', label: '系统诊断', icon: Stethoscope },
]

const currentTitle = computed(() => {
  const item = navItems.find(i => route.path === i.path)
  if (item) return item.label
  if (route.path === '/admin') return '系统概览'
  return '管理后台'
})

const navClass = (active: boolean) => [
  'flex h-10 items-center gap-2 rounded px-3 text-sm transition-colors',
  active ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
]

const logout = () => {
  userStore.logout()
}
</script>
