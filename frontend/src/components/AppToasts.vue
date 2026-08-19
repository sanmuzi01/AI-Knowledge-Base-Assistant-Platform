<template>
  <div class="fixed right-4 top-4 z-[80] w-[320px] max-w-[calc(100vw-32px)] space-y-2">
    <div
      v-for="item in items"
      :key="item.id"
      :class="toastClass(item.type)"
      class="rounded-lg border bg-white px-4 py-3 text-sm shadow-lg"
    >
      {{ item.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { ToastMessage, ToastType } from '../utils/toast'

const items = ref<ToastMessage[]>([])
let nextId = 1

const toastClass = (type: ToastType) => ({
  success: 'border-emerald-200 text-emerald-700',
  error: 'border-red-200 text-red-700',
  info: 'border-blue-200 text-blue-700',
}[type])

const onToast = (event: Event) => {
  const detail = (event as CustomEvent).detail || {}
  const item: ToastMessage = {
    id: nextId++,
    type: detail.type || 'info',
    message: detail.message || '',
  }
  if (!item.message) return
  items.value.push(item)
  window.setTimeout(() => {
    items.value = items.value.filter((current) => current.id !== item.id)
  }, 3200)
}

onMounted(() => window.addEventListener('app-toast', onToast))
onBeforeUnmount(() => window.removeEventListener('app-toast', onToast))
</script>
