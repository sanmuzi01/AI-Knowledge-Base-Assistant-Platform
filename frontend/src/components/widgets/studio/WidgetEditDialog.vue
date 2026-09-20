<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="emit('close')">
    <div class="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
      <h3 class="text-sm font-semibold text-slate-900">编辑小窗口</h3>
      <label class="mt-3 block text-xs text-slate-500">名称</label>
      <input v-model="name" class="mt-1 w-full rounded border border-sky-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
      <label class="mt-3 block text-xs text-slate-500">备注（可选）</label>
      <input v-model="desc" class="mt-1 w-full rounded border border-sky-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
      <div class="mt-4 flex justify-end gap-2">
        <button @click="emit('close')" class="rounded border border-sky-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-sky-50">取消</button>
        <button @click="save" :disabled="saving" class="ui-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { updateWidget, type WidgetItem } from '../../../api/widget'
import { getErrorMessage } from '../../../utils/request'
import { toastError } from '../../../utils/toast'

const props = defineProps<{ widget: WidgetItem }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved'): void }>()

const name = ref(props.widget.name)
const desc = ref(props.widget.description)
const saving = ref(false)

async function save() {
  saving.value = true
  try {
    await updateWidget(props.widget.id, { name: name.value.trim(), description: desc.value.trim() })
    emit('saved')
  } catch (e: any) {
    toastError(getErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>
