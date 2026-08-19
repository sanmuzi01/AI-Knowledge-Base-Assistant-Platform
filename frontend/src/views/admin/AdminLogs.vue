<template>
  <div class="p-6">
    <p class="text-xs text-slate-500 mb-4">操作日志查询：用户操作、API 调用、错误记录</p>
    <div class="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center">
      <ScrollText :size="36" class="mx-auto text-slate-300 mb-3" />
      <p class="text-base font-medium text-slate-700 mb-1">操作日志</p>
      <p class="text-xs text-slate-400">M7 阶段实现：OperationLog 表 + 采集中间件 + 按用户/时间/类型筛选</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ScrollText } from 'lucide-vue-next'
</script>
