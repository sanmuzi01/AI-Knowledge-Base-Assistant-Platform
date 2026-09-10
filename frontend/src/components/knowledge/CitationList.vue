<template>
  <div v-if="citations && citations.length" class="mt-2">
    <div class="flex flex-wrap items-center gap-1.5">
      <span class="text-xs text-gray-400">参考来源：</span>
      <button
        v-for="c in citations"
        :key="c.index"
        type="button"
        class="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs transition"
        :class="openIdx === c.index
          ? 'border-blue-300 bg-blue-50 text-blue-700'
          : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-blue-300 hover:text-blue-700'"
        :title="c.space_name ? `${c.space_name} / ${c.file_name}` : c.file_name"
        @click="toggle(c.index)"
      >
        <span class="font-medium">【来源{{ c.index }}】</span>
        <span class="max-w-[12rem] truncate">{{ c.file_name }}</span>
      </button>
    </div>

    <div
      v-if="current"
      class="mt-1.5 rounded border border-blue-100 bg-blue-50/50 px-3 py-2 text-xs leading-relaxed text-gray-700"
    >
      <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-gray-500">
        <span class="truncate">
          【来源{{ current.index }}】{{ current.space_name ? current.space_name + ' / ' : '' }}{{ current.file_name }}
        </span>
        <button
          v-if="current.space_id"
          class="shrink-0 text-blue-600 hover:underline"
          @click="goSpace(current)"
        >打开知识库 ↗</button>
      </div>
      <p v-if="current.snippet" class="whitespace-pre-wrap">{{ current.snippet }}<span v-if="snippetTruncated">…</span></p>
      <p v-else class="text-gray-400">这条来源没有可显示的片段。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Citation } from '../../api/chat'

const props = defineProps<{ citations?: Citation[]; openIndex?: number | null }>()

const router = useRouter()
const openIdx = ref<number | null>(null)

// 正文里点 【来源N】 时，父组件把编号透过来
watch(
  () => props.openIndex,
  (v) => {
    if (v != null && props.citations?.some((c) => c.index === v)) openIdx.value = v
  },
)

const current = computed(() => props.citations?.find((c) => c.index === openIdx.value) ?? null)
const snippetTruncated = computed(() => (current.value?.snippet?.length ?? 0) >= 300)

function toggle(idx: number) {
  openIdx.value = openIdx.value === idx ? null : idx
}

function goSpace(c: Citation) {
  if (c.space_id) router.push(`/knowledge-spaces/${c.space_id}`)
}
</script>
