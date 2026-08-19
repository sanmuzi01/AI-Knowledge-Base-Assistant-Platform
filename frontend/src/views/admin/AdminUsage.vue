<template>
  <div class="p-6">
    <p class="text-xs text-slate-500 mb-4">系统使用情况统计：调用趋势、Token 用量、活跃用户排行</p>
    <div class="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center">
      <BarChart3 :size="36" class="mx-auto text-slate-300 mb-3" />
      <p class="text-base font-medium text-slate-700 mb-1">使用情况分析</p>
      <p class="text-xs text-slate-400">M6 阶段实现：调用趋势图、Token 用量统计、活跃用户排行、资源占用趋势</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { BarChart3 } from 'lucide-vue-next'
</script>
