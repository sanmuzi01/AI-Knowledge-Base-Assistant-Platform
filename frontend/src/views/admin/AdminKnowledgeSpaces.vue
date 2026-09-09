<template>
  <div class="space-y-4">
    <header>
      <h1 class="text-lg font-semibold text-slate-900">企业知识库</h1>
      <p class="mt-1 text-sm text-slate-500">平台内所有知识库空间的归属、规模、成员和健康分。</p>
    </header>

    <div v-if="loading" class="py-12 text-center text-sm text-slate-400">加载中…</div>
    <div v-else-if="err" class="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ err }}</div>
    <div v-else class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table class="min-w-full text-sm">
        <thead class="bg-slate-50 text-xs text-slate-500">
          <tr>
            <th class="px-3 py-2 text-left">空间</th>
            <th class="px-3 py-2 text-left">所有者</th>
            <th class="px-3 py-2 text-right">文档</th>
            <th class="px-3 py-2 text-right">片段</th>
            <th class="px-3 py-2 text-right">成员</th>
            <th class="px-3 py-2 text-right">绑定 Agent</th>
            <th class="px-3 py-2 text-right">健康分</th>
            <th class="px-3 py-2 text-left">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="s in items" :key="s.id" class="hover:bg-slate-50">
            <td class="px-3 py-2">
              <div class="font-medium text-slate-800">{{ s.name }}</div>
              <div class="text-xs text-slate-400">#{{ s.id }}<span v-if="s.organization_id"> · org {{ s.organization_id }}</span></div>
            </td>
            <td class="px-3 py-2 text-slate-600">{{ s.owner_name || ('#' + s.owner_user_id) }}</td>
            <td class="px-3 py-2 text-right">{{ s.doc_count }}</td>
            <td class="px-3 py-2 text-right">{{ s.chunk_count }}</td>
            <td class="px-3 py-2 text-right">{{ s.member_count }}</td>
            <td class="px-3 py-2 text-right">{{ s.bound_agent_count }}</td>
            <td class="px-3 py-2 text-right">
              <span :class="healthColor(s.health_score)">{{ s.health_score ?? '—' }}</span>
            </td>
            <td class="px-3 py-2">
              <span class="rounded px-2 py-0.5 text-xs"
                :class="s.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'">
                {{ s.status === 'active' ? '启用' : '归档' }}
              </span>
            </td>
          </tr>
          <tr v-if="items.length === 0"><td colspan="8" class="px-3 py-8 text-center text-slate-400">暂无知识库空间</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listAdminKnowledgeSpaces, type AdminKnowledgeSpace } from '../../api/admin'
import { getErrorMessage } from '../../utils/request'

const loading = ref(true)
const err = ref('')
const items = ref<AdminKnowledgeSpace[]>([])

const healthColor = (n: number | null) =>
  n == null ? 'text-slate-300'
    : n >= 80 ? 'text-emerald-600 font-semibold'
    : n >= 55 ? 'text-amber-600 font-semibold' : 'text-red-600 font-semibold'

onMounted(async () => {
  try {
    items.value = (await listAdminKnowledgeSpaces()).items
  } catch (e: any) {
    err.value = getErrorMessage(e, '加载失败')
  } finally {
    loading.value = false
  }
})
</script>
