<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-5">
      <p class="text-xs text-slate-500">配置套餐与每月 Token 配额；用户在「用户管理」页分配套餐。</p>
      <div class="flex gap-2">
        <button
          @click="load"
          :disabled="loading"
          class="inline-flex items-center gap-2 rounded border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
        >
          <RefreshCcw :size="14" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <button
          @click="openCreate"
          class="inline-flex items-center gap-2 rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
        >
          <Plus :size="14" />
          新建套餐
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ errorMsg }}</p>

    <div v-if="loading" class="py-12 text-center text-sm text-slate-400">加载中…</div>
    <section v-else class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table class="w-full min-w-[720px] text-left text-sm">
        <thead class="border-b border-slate-100 bg-slate-50 text-xs text-slate-500">
          <tr>
            <th class="px-4 py-3 font-medium">套餐</th>
            <th class="px-4 py-3 font-medium">月度 Token 配额</th>
            <th class="px-4 py-3 font-medium">价格说明</th>
            <th class="px-4 py-3 font-medium">状态</th>
            <th class="px-4 py-3 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in plans" :key="p.id" class="border-b border-slate-100 hover:bg-slate-50/50">
            <td class="px-4 py-3">
              <p class="font-medium text-slate-900">{{ p.display_name }}</p>
              <p class="text-xs text-slate-400">标识 {{ p.name }} · #{{ p.id }}</p>
            </td>
            <td class="px-4 py-3 text-slate-700">
              {{ p.monthly_token_limit > 0 ? p.monthly_token_limit.toLocaleString() + ' / 月' : '不限量' }}
            </td>
            <td class="px-4 py-3 text-slate-500">{{ p.price_desc || '-' }}</td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span v-if="p.is_default" class="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">默认套餐</span>
                <span
                  class="rounded px-2 py-0.5 text-xs"
                  :class="p.is_enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
                >{{ p.is_enabled ? '启用中' : '已停用' }}</span>
              </div>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1.5">
                <button @click="openEdit(p)" class="rounded border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50">
                  编辑
                </button>
                <button
                  v-if="!p.is_default"
                  @click="setDefault(p)"
                  class="rounded border border-indigo-200 px-2.5 py-1 text-xs text-indigo-700 hover:bg-indigo-50"
                >
                  设为默认
                </button>
                <button
                  @click="toggleEnabled(p)"
                  class="rounded border px-2.5 py-1 text-xs transition-colors"
                  :class="p.is_enabled ? 'border-red-200 text-red-700 hover:bg-red-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'"
                >
                  {{ p.is_enabled ? '停用' : '启用' }}
                </button>
                <button
                  v-if="!p.is_default"
                  @click="removePlan(p)"
                  class="rounded border border-red-200 px-2.5 py-1 text-xs text-red-700 hover:bg-red-50"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!plans.length"><td colspan="5" class="px-4 py-8 text-center text-slate-400">还没有配置任何套餐</td></tr>
        </tbody>
      </table>
    </section>

    <!-- 新建/编辑弹窗 -->
    <div v-if="dialog.visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closeDialog">
      <div class="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h3 class="mb-4 text-base font-semibold text-slate-800">{{ dialog.editing ? '编辑套餐' : '新建套餐' }}</h3>
        <div class="space-y-3">
          <div v-if="!dialog.editing">
            <label class="mb-1 block text-xs text-slate-500">套餐标识（程序内唯一，创建后不可改）</label>
            <input v-model="dialog.form.name" type="text" placeholder="如 pro"
              class="h-9 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-indigo-500" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-500">展示名</label>
            <input v-model="dialog.form.display_name" type="text" placeholder="如 专业版"
              class="h-9 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-indigo-500" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-500">每月 Token 配额（0 = 不限量）</label>
            <input v-model.number="dialog.form.monthly_token_limit" type="number" min="0"
              class="h-9 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-indigo-500" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-slate-500">价格说明（纯展示，不接支付）</label>
            <input v-model="dialog.form.price_desc" type="text" placeholder="如 ¥99/月"
              class="h-9 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-indigo-500" />
          </div>
          <label class="flex items-center gap-2 text-sm text-slate-600">
            <input v-model="dialog.form.is_default" type="checkbox" class="h-4 w-4 rounded border-slate-300" />
            设为默认套餐（未订阅的用户会落到这个套餐）
          </label>
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <button @click="closeDialog" class="rounded px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">取消</button>
          <button
            @click="submitDialog"
            :disabled="acting || !dialog.form.display_name || (!dialog.editing && !dialog.form.name)"
            class="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Plus, RefreshCcw } from 'lucide-vue-next'
import * as adminApi from '../../api/admin'
import type { AdminPlan } from '../../api/admin'
import { getErrorMessage } from '../../utils/request'

const plans = ref<AdminPlan[]>([])
const loading = ref(true)
const errorMsg = ref('')
const acting = ref(false)

const dialog = ref<{
  visible: boolean
  editing: AdminPlan | null
  form: { name: string; display_name: string; monthly_token_limit: number; price_desc: string; is_default: boolean }
}>({
  visible: false,
  editing: null,
  form: { name: '', display_name: '', monthly_token_limit: 0, price_desc: '', is_default: false },
})

const load = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    plans.value = await adminApi.listAdminPlans()
  } catch (e: any) {
    errorMsg.value = getErrorMessage(e, '加载套餐列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  dialog.value = {
    visible: true,
    editing: null,
    form: { name: '', display_name: '', monthly_token_limit: 0, price_desc: '', is_default: false },
  }
}

const openEdit = (p: AdminPlan) => {
  dialog.value = {
    visible: true,
    editing: p,
    form: {
      name: p.name, display_name: p.display_name, monthly_token_limit: p.monthly_token_limit,
      price_desc: p.price_desc || '', is_default: p.is_default,
    },
  }
}

const closeDialog = () => {
  dialog.value.visible = false
}

const submitDialog = async () => {
  acting.value = true
  try {
    if (dialog.value.editing) {
      await adminApi.updateAdminPlan(dialog.value.editing.id, {
        display_name: dialog.value.form.display_name,
        monthly_token_limit: dialog.value.form.monthly_token_limit,
        price_desc: dialog.value.form.price_desc || undefined,
        is_default: dialog.value.form.is_default || undefined,
      })
    } else {
      await adminApi.createAdminPlan({
        name: dialog.value.form.name,
        display_name: dialog.value.form.display_name,
        monthly_token_limit: dialog.value.form.monthly_token_limit,
        price_desc: dialog.value.form.price_desc || undefined,
        is_default: dialog.value.form.is_default,
      })
    }
    closeDialog()
    await load()
  } catch (e: any) {
    alert(getErrorMessage(e, '保存失败'))
  } finally {
    acting.value = false
  }
}

const setDefault = async (p: AdminPlan) => {
  if (!confirm(`确认把「${p.display_name}」设为默认套餐？`)) return
  try {
    await adminApi.updateAdminPlan(p.id, { is_default: true })
    await load()
  } catch (e: any) {
    alert(getErrorMessage(e, '设置失败'))
  }
}

const toggleEnabled = async (p: AdminPlan) => {
  try {
    await adminApi.updateAdminPlan(p.id, { is_enabled: !p.is_enabled })
    await load()
  } catch (e: any) {
    alert(getErrorMessage(e, '操作失败'))
  }
}

const removePlan = async (p: AdminPlan) => {
  if (!confirm(`确认删除套餐「${p.display_name}」？如果还有用户订阅它，会被拒绝。`)) return
  try {
    await adminApi.deleteAdminPlan(p.id)
    await load()
  } catch (e: any) {
    alert(getErrorMessage(e, '删除失败'))
  }
}

onMounted(load)
</script>
