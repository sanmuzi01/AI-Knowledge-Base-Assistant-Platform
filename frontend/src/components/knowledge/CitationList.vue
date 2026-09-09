<template>
  <div v-if="citations && citations.length" class="mt-2 flex flex-wrap items-center gap-1.5">
    <span class="text-xs text-gray-400">参考来源：</span>
    <button
      v-for="c in citations"
      :key="c.index"
      type="button"
      class="inline-flex items-center gap-1 rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600 hover:border-blue-300 hover:text-blue-700"
      :title="c.space_name ? `${c.space_name} / ${c.file_name}` : c.file_name"
      @click="open(c)"
    >
      <span class="font-medium">【来源{{ c.index }}】</span>
      <span class="max-w-[12rem] truncate">{{ c.file_name }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { Citation } from '../../api/chat'

defineProps<{ citations?: Citation[] }>()

const router = useRouter()

const open = (c: Citation) => {
  if (c.space_id) router.push(`/knowledge-spaces/${c.space_id}`)
}
</script>
