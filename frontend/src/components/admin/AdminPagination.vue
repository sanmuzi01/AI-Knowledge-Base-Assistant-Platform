<template>
  <div v-if="total > 0" class="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
    <span>共 {{ total }} 条 · 第 {{ currentPage }}/{{ totalPages }} 页</span>
    <div class="flex gap-2">
      <button
        type="button"
        :disabled="offset <= 0"
        @click="$emit('update:offset', Math.max(0, offset - limit))"
        class="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
      >上一页</button>
      <button
        type="button"
        :disabled="offset + limit >= total"
        @click="$emit('update:offset', offset + limit)"
        class="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
      >下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ total: number; limit: number; offset: number }>()
defineEmits<{ 'update:offset': [value: number] }>()

const currentPage = computed(() => Math.floor(props.offset / Math.max(1, props.limit)) + 1)
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.limit))))
</script>
