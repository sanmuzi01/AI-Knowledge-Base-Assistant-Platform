<template>
  <div class="flex flex-wrap items-center gap-1">
    <RouterLink
      v-for="t in tabs"
      :key="t.path"
      :to="t.path"
      :class="[
        'rounded px-3 py-1.5 text-sm font-medium transition-colors',
        isActive(t.path)
          ? 'bg-sky-100 text-sky-800 ring-1 ring-sky-200'
          : 'text-slate-600 hover:bg-sky-50 hover:text-slate-900',
      ]"
    >
      {{ t.label }}
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const props = defineProps<{ tabs: { label: string; path: string; match?: string }[] }>()
const route = useRoute()

const isActive = (path: string) => {
  const tab = props.tabs.find((t) => t.path === path)
  return route.path === path || (tab?.match ? route.path.startsWith(tab.match) : false)
}
</script>
