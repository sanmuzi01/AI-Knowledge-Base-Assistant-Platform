<template>
  <div class="flex h-full flex-col justify-center p-4">
    <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
    <pre v-else-if="result" class="max-h-full overflow-auto rounded bg-slate-50 p-2 text-[11px] text-slate-600">{{ pretty }}</pre>
    <p v-else class="text-sm text-slate-400">这种展示形态还没有专用样式。</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'

const props = defineProps<{ widget: WidgetItem; result: any; error?: string }>()
const pretty = computed(() => {
  try {
    return JSON.stringify(props.result, null, 2)
  } catch {
    return String(props.result)
  }
})
</script>
