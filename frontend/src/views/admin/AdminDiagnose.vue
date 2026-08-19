<template>
  <div class="p-6">
    <p class="text-xs text-slate-500 mb-4">系统诊断：检查数据库、端口、模型 Key、向量库目录、任务失败原因</p>
    <div class="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center">
      <Stethoscope :size="36" class="mx-auto text-slate-300 mb-3" />
      <p class="text-base font-medium text-slate-700 mb-1">系统诊断</p>
      <p class="text-xs text-slate-400">后续实现：数据库连通性、模型 Key 可用性、向量库目录、磁盘占用、失败任务归因</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Stethoscope } from 'lucide-vue-next'
</script>
