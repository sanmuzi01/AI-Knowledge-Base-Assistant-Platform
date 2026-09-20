<template>
  <button
    type="button"
    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-black/[.06] hover:text-slate-900"
    :title="isDark ? '切换到浅色' : '切换到深色'"
    :aria-label="isDark ? '切换到浅色' : '切换到深色'"
    @click="toggleTheme"
  >
    <component :is="isDark ? Sun : Moon" :size="16" :stroke-width="1.8" />
  </button>
</template>

<script setup lang="ts">
import { Moon, Sun } from 'lucide-vue-next'
import { isDark, toggleTheme } from '../utils/theme'
</script>
