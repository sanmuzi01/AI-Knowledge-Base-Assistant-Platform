<template>
  <section class="rounded-lg border border-sky-200 bg-white/80 p-4">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-slate-900">成员与权限</h2>
      <button v-if="canManage" @click="showAudit = !showAudit"
        class="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50">
        {{ showAudit ? '隐藏操作日志' : '操作日志' }}
      </button>
    </div>

    <div v-if="loading" class="py-4 text-center text-xs text-slate-400">加载中…</div>
    <template v-else-if="data">
      <ul class="divide-y divide-slate-100 text-sm">
        <li class="flex items-center gap-2 py-2">
          <span class="min-w-0 flex-1 truncate">{{ data.owner.user_name || ('#' + data.owner.user_id) }}</span>
          <span class="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">所有者</span>
        </li>
        <li v-for="m in data.members" :key="m.user_id" class="flex items-center gap-2 py-2">
          <span class="min-w-0 flex-1 truncate">{{ m.user_name || ('#' + m.user_id) }}</span>
          <select v-if="canManage" :value="m.role" @change="changeRole(m, $event)"
            class="rounded border border-slate-200 px-1.5 py-0.5 text-xs">
            <option v-for="r in data.assignable_roles" :key="r" :value="r">{{ roleLabel(r) }}</option>
          </select>
          <span v-else class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{{ roleLabel(m.role) }}</span>
          <button v-if="canManage" @click="remove(m)" class="rounded px-1.5 py-0.5 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600">移除</button>
        </li>
        <li v-if="data.members.length === 0" class="py-3 text-center text-xs text-slate-400">还没有其他成员</li>
      </ul>

      <div v-if="canManage" class="mt-3 flex flex-wrap items-center gap-2">
        <input v-model="newName" placeholder="用户名" class="h-8 flex-1 rounded border border-slate-300 px-2 text-sm" />
        <select v-model="newRole" class="h-8 rounded border border-slate-300 px-1.5 text-sm">
          <option value="viewer">只读</option>
          <option value="editor">可管文档</option>
          <option value="admin">管理员</option>
        </select>
        <button @click="add" :disabled="!newName.trim() || adding"
          class="h-8 rounded bg-blue-600 px-3 text-sm text-white hover:bg-blue-700 disabled:bg-blue-300">添加</button>
      </div>
      <p v-if="msg" class="mt-2 text-xs" :class="msgErr ? 'text-red-600' : 'text-emerald-600'">{{ msg }}</p>

      <div v-if="showAudit" class="mt-4 border-t border-slate-100 pt-3">
        <p class="mb-1 text-xs font-semibold text-slate-600">最近操作</p>
        <ul class="max-h-56 space-y-1 overflow-y-auto text-xs text-slate-500">
          <li v-for="a in audit" :key="a.id" class="flex gap-2">
            <span class="text-slate-400">{{ a.created_at }}</span>
            <span class="text-slate-700">{{ a.user_name || ('#' + a.user_id) }}</span>
            <span>{{ actionLabel(a.action) }}</span>
            <span v-if="a.detail" class="truncate text-slate-400">{{ a.detail }}</span>
          </li>
          <li v-if="audit.length === 0" class="text-slate-400">暂无记录</li>
        </ul>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import * as ksApi from '../../api/knowledgeSpace'
import type { SpaceMemberList, SpaceAuditEntry, SpaceMember } from '../../api/knowledgeSpace'
import { getErrorMessage } from '../../utils/request'

const props = defineProps<{ spaceId: number; canManage: boolean }>()

const loading = ref(true)
const data = ref<SpaceMemberList | null>(null)
const audit = ref<SpaceAuditEntry[]>([])
const showAudit = ref(false)
const newName = ref('')
const newRole = ref('viewer')
const adding = ref(false)
const msg = ref('')
const msgErr = ref(false)

const ROLE_LABEL: Record<string, string> = { owner: '所有者', admin: '管理员', editor: '可管文档', viewer: '只读' }
const roleLabel = (r: string) => ROLE_LABEL[r] || r
const ACTION_LABEL: Record<string, string> = {
  'space.update': '修改空间', 'space.delete': '删除空间',
  'doc.upload': '上传文档', 'doc.upload_batch': '批量上传', 'doc.crawl': '抓取网页',
  'doc.delete': '删除文档', 'doc.reindex': '重建索引', 'doc.set_enabled': '启停文档',
  'doc.update_meta': '改文档信息', 'member.set': '设置成员', 'member.remove': '移除成员',
}
const actionLabel = (a: string) => ACTION_LABEL[a] || a

const load = async () => {
  loading.value = true
  try {
    data.value = await ksApi.listSpaceMembers(props.spaceId)
  } catch (e: any) {
    msg.value = getErrorMessage(e, '加载成员失败'); msgErr.value = true
  } finally {
    loading.value = false
  }
}

const loadAudit = async () => {
  try { audit.value = (await ksApi.listSpaceAudit(props.spaceId)).items } catch { audit.value = [] }
}

watch(showAudit, (v) => { if (v) loadAudit() })

const flash = (text: string, err = false) => { msg.value = text; msgErr.value = err; setTimeout(() => (msg.value = ''), 3000) }

const add = async () => {
  adding.value = true
  try {
    await ksApi.setSpaceMember(props.spaceId, { user_name: newName.value.trim(), role: newRole.value })
    newName.value = ''
    await load()
    flash('已添加')
  } catch (e: any) {
    flash(getErrorMessage(e, '添加失败'), true)
  } finally {
    adding.value = false
  }
}

const changeRole = async (m: SpaceMember, e: Event) => {
  const role = (e.target as HTMLSelectElement).value
  try {
    await ksApi.setSpaceMember(props.spaceId, { user_name: m.user_name, role })
    await load()
    flash('已更新')
  } catch (err: any) {
    flash(getErrorMessage(err, '更新失败'), true)
    await load()
  }
}

const remove = async (m: SpaceMember) => {
  if (!confirm(`移除成员 ${m.user_name}？`)) return
  try {
    await ksApi.removeSpaceMember(props.spaceId, m.user_id)
    await load()
    flash('已移除')
  } catch (e: any) {
    flash(getErrorMessage(e, '移除失败'), true)
  }
}

onMounted(load)
</script>
