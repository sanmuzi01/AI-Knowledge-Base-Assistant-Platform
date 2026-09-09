<template>
  <!-- 导出 -->
  <div v-if="mode === 'export'" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
      <h3 class="text-sm font-semibold text-slate-900">导出小窗口配置</h3>
      <p class="mt-1 text-xs text-slate-500">复制下面的内容，发给别人 → 对方用「导入」粘贴即可得到同样的小窗口。</p>
      <textarea :value="json" readonly rows="10"
        class="mt-3 w-full resize-none rounded border border-sky-200 bg-slate-50 p-2 font-mono text-[11px] text-slate-700 outline-none"></textarea>
      <div class="mt-3 flex justify-end gap-2">
        <button @click="emit('close')" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">关闭</button>
        <button @click="copy" class="sci-primary inline-flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-white">
          <Copy :size="13" />{{ copied ? '已复制' : '复制' }}
        </button>
      </div>
    </div>
  </div>

  <!-- 导入 -->
  <div v-else-if="mode === 'import'" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl">
      <h3 class="text-sm font-semibold text-slate-900">导入小窗口</h3>
      <p class="mt-1 text-xs text-slate-500">把别人导出的 JSON 粘贴到这里。</p>
      <textarea v-model="text" rows="10" placeholder='{"export_version": 1, "spec": { … }}'
        class="mt-3 w-full resize-none rounded border border-sky-200 bg-white p-2 font-mono text-[11px] text-slate-700 outline-none focus:border-sky-400"></textarea>
      <p v-if="error" class="mt-2 text-xs text-red-600">{{ error }}</p>
      <div class="mt-3 flex justify-end gap-2">
        <button @click="emit('close')" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">取消</button>
        <button @click="doImport" :disabled="importing || !text.trim()"
          class="sci-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
          {{ importing ? '导入中…' : '导入' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Copy } from 'lucide-vue-next'
import { importWidget } from '../../../api/widget'
import { getErrorMessage } from '../../../utils/request'
import { toastError, toastSuccess } from '../../../utils/toast'

const props = defineProps<{ mode: 'import' | 'export' | null; json?: string }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'imported'): void }>()

const copied = ref(false)
const text = ref('')
const error = ref('')
const importing = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.json || '')
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    toastError('复制失败，请手动选择文本复制')
  }
}

async function doImport() {
  error.value = ''
  let parsed: any
  try {
    parsed = JSON.parse(text.value)
  } catch {
    error.value = '不是有效的 JSON'
    return
  }
  importing.value = true
  try {
    await importWidget(parsed)
    toastSuccess('已导入')
    text.value = ''
    emit('imported')
  } catch (e: any) {
    error.value = getErrorMessage(e, '导入失败')
  } finally {
    importing.value = false
  }
}
</script>
