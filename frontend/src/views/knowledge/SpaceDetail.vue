<template>
  <div class="flex h-screen flex-col bg-transparent text-slate-950">
    <header class="border-b border-sky-200/70 bg-white/80 px-5 py-4 shadow-sm backdrop-blur-xl lg:px-8">
      <div class="mx-auto flex max-w-6xl items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <button
            @click="router.push('/knowledge-spaces')"
            class="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
            title="返回知识库中心"
          >
            <ArrowLeft :size="16" />
          </button>
          <div>
            <h1 class="text-xl font-semibold">{{ space?.name || '知识库空间' }}</h1>
            <p class="mt-1 text-sm text-slate-500">
              {{ space?.purpose_label || '知识库' }} ·
              文档 {{ space?.doc_count ?? 0 }} · 片段 {{ space?.chunk_count ?? 0 }}
              <span v-if="space?.last_indexed_at"> · 最近入库 {{ space.last_indexed_at }}</span>
            </p>
          </div>
        </div>
        <div class="flex shrink-0 gap-2">
          <button
            @click="router.push(`/knowledge-spaces/${spaceId}/health`)"
            class="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            健康报告
          </button>
          <button
            @click="router.push(`/knowledge-spaces/${spaceId}/debug`)"
            class="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            调试台
          </button>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl flex-1 overflow-y-auto p-5 lg:p-8">
      <p v-if="space && space.my_role !== 'owner'" class="mb-3 rounded border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-700">
        你在这个共享知识库里的身份：<b>{{ roleLabel(space.my_role) }}</b>{{ space.can_write_doc ? '' : '（只读，不能改动文档）' }}
      </p>

      <!-- 添加资料 -->
      <section v-if="!space || space.can_write_doc !== false" class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <h2 class="text-sm font-semibold text-slate-900">上传文档</h2>
          <p class="mt-1 text-xs text-slate-500">支持 PDF / Word / TXT / Markdown，可多选。</p>
          <input type="file" multiple accept=".pdf,.docx,.txt,.md" class="mt-3 block w-full text-xs" @change="onFiles" />
          <p v-if="uploadMsg" class="mt-2 text-xs" :class="uploadMsg.err ? 'text-red-600' : 'text-emerald-600'">{{ uploadMsg.text }}</p>
        </div>
        <div class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <h2 class="text-sm font-semibold text-slate-900">抓取网页</h2>
          <p class="mt-1 text-xs text-slate-500">每行一个公开网址，抓取正文入库。</p>
          <textarea v-model="urlText" rows="3" placeholder="https://example.com/policy"
            class="mt-3 w-full resize-none rounded border border-sky-200 px-2 py-1.5 text-xs outline-none focus:border-sky-400"></textarea>
          <button @click="onCrawl" :disabled="crawling || !urlText.trim()"
            class="sci-primary mt-2 rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40">
            {{ crawling ? '抓取中…' : '抓取并入库' }}
          </button>
          <p v-if="crawlMsg" class="mt-2 text-xs" :class="crawlMsg.err ? 'text-red-600' : 'text-emerald-600'">{{ crawlMsg.text }}</p>
        </div>
      </section>

      <!-- 筛选 -->
      <section class="mt-6 flex flex-wrap items-center gap-2 text-xs">
        <select v-model="filter.category" @change="reloadDocs" class="rounded border border-sky-200 px-2 py-1">
          <option value="">全部分类</option>
          <option v-for="c in facets.categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="filter.tag" @change="reloadDocs" class="rounded border border-sky-200 px-2 py-1">
          <option value="">全部标签</option>
          <option v-for="t in facets.tags" :key="t" :value="t">{{ t }}</option>
        </select>
        <select v-model="filter.doc_status" @change="reloadDocs" class="rounded border border-sky-200 px-2 py-1">
          <option value="">全部状态</option>
          <option v-for="s in facets.statuses" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
        <label class="flex items-center gap-1">
          <input type="checkbox" v-model="onlyEnabled" @change="reloadDocs" /> 只看启用
        </label>
        <button @click="reloadDocs" class="rounded border border-sky-200 px-2 py-1 hover:bg-sky-50">刷新</button>
        <span class="text-slate-400">共 {{ total }} 份</span>
      </section>

      <!-- 文档表 -->
      <section class="mt-3 overflow-x-auto rounded-lg border border-slate-100">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">文件</th>
              <th class="px-3 py-2 font-medium">分类 / 标签 / 版本</th>
              <th class="px-3 py-2 font-medium">状态</th>
              <th class="px-3 py-2 font-medium">片段</th>
              <th class="px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!docs.length"><td colspan="5" class="px-3 py-8 text-center text-slate-400">暂无文档</td></tr>
            <tr v-for="d in docs" :key="d.id" class="border-t border-slate-100 align-top">
              <td class="px-3 py-2">
                <p class="font-medium text-slate-800">{{ d.file_name }}</p>
                <p class="text-[11px] text-slate-400">{{ d.source_type }} · {{ d.created_at }}</p>
                <a v-if="d.source_url" :href="d.source_url" target="_blank" class="text-[11px] text-sky-600 hover:underline">来源链接</a>
              </td>
              <td class="px-3 py-2">
                <input :value="d.category || ''" placeholder="分类" @change="saveMeta(d, { category: ($event.target as HTMLInputElement).value })"
                  class="w-24 rounded border border-slate-200 px-1 py-0.5" />
                <input :value="d.tags.join(', ')" placeholder="标签,逗号" @change="saveMeta(d, { tags: ($event.target as HTMLInputElement).value.split(',').map(s=>s.trim()).filter(Boolean) })"
                  class="ml-1 w-28 rounded border border-slate-200 px-1 py-0.5" />
                <input :value="d.version || ''" placeholder="版本" @change="saveMeta(d, { version: ($event.target as HTMLInputElement).value })"
                  class="ml-1 w-16 rounded border border-slate-200 px-1 py-0.5" />
              </td>
              <td class="px-3 py-2">
                <span :class="d.status === 'done' ? 'text-emerald-600' : d.status === 'failed' ? 'text-red-500' : 'text-sky-600'">
                  {{ d.status_label }}
                </span>
                <p v-if="d.error_msg" class="max-w-[200px] text-[11px] text-red-500">{{ d.error_msg }}</p>
              </td>
              <td class="px-3 py-2 text-slate-600">{{ d.chunk_count }}</td>
              <td class="px-3 py-2 whitespace-nowrap">
                <button @click="toggleEnabled(d)" class="text-sky-600 hover:underline">{{ d.is_enabled ? '禁用' : '启用' }}</button>
                <button @click="reindex(d)" class="ml-2 text-sky-600 hover:underline">重建</button>
                <button @click="removeDoc(d)" class="ml-2 text-red-500 hover:underline">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <SpaceMembersPanel
        v-if="space"
        class="mt-6"
        :space-id="spaceId"
        :can-manage="!!space.can_manage"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import {
  crawlSpaceDocs, deleteSpaceDoc, getSpace, listSpaceDocs, reindexSpaceDoc,
  updateSpaceDoc, uploadSpaceDoc,
  type KnowledgeSpace, type SpaceDoc,
} from '../../api/knowledgeSpace'
import SpaceMembersPanel from '../../components/knowledge/SpaceMembersPanel.vue'

const ROLE_LABEL: Record<string, string> = { owner: '所有者', admin: '管理员', editor: '可管文档', viewer: '只读' }
const roleLabel = (r: string) => ROLE_LABEL[r] || r
import { getErrorMessage } from '../../utils/request'
import { toastError, toastSuccess } from '../../utils/toast'

const route = useRoute()
const router = useRouter()
const spaceId = Number(route.params.id)

const space = ref<KnowledgeSpace | null>(null)
const docs = ref<SpaceDoc[]>([])
const total = ref(0)
const facets = ref<{ categories: string[]; tags: string[]; statuses: { key: string; label: string }[] }>({
  categories: [], tags: [], statuses: [],
})
const filter = reactive({ category: '', tag: '', doc_status: '' })
const onlyEnabled = ref(false)

const urlText = ref('')
const crawling = ref(false)
const uploadMsg = ref<{ text: string; err: boolean } | null>(null)
const crawlMsg = ref<{ text: string; err: boolean } | null>(null)

async function reloadSpace() {
  try {
    space.value = await getSpace(spaceId)
  } catch (e: any) {
    toastError(getErrorMessage(e, '加载空间失败'))
    router.push('/knowledge-spaces')
  }
}

async function reloadDocs() {
  try {
    const res = await listSpaceDocs(spaceId, {
      category: filter.category || undefined,
      tag: filter.tag || undefined,
      doc_status: filter.doc_status || undefined,
      enabled: onlyEnabled.value ? true : undefined,
    })
    docs.value = res.items
    total.value = res.total
    facets.value = res.facets
  } catch (e: any) {
    toastError(getErrorMessage(e, '加载文档失败'))
  }
}

async function onFiles(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  if (!files.length) return
  uploadMsg.value = null
  let ok = 0
  for (const f of files) {
    try {
      await uploadSpaceDoc(spaceId, f)
      ok++
    } catch (err: any) {
      uploadMsg.value = { text: getErrorMessage(err, `上传 ${f.name} 失败`), err: true }
    }
  }
  ;(e.target as HTMLInputElement).value = ''
  if (ok) uploadMsg.value = { text: `已创建 ${ok} 个入库任务，稍后刷新查看`, err: false }
  await Promise.all([reloadSpace(), reloadDocs()])
}

async function onCrawl() {
  const urls = urlText.value.split('\n').map((u) => u.trim()).filter(Boolean)
  if (!urls.length) return
  crawling.value = true
  crawlMsg.value = null
  try {
    const res = await crawlSpaceDocs(spaceId, urls)
    crawlMsg.value = { text: `已入库任务 ${res.count} 个${res.failed_count ? `，失败 ${res.failed_count}` : ''}`, err: false }
    urlText.value = ''
    await Promise.all([reloadSpace(), reloadDocs()])
  } catch (e: any) {
    crawlMsg.value = { text: getErrorMessage(e, '抓取失败'), err: true }
  } finally {
    crawling.value = false
  }
}

async function saveMeta(d: SpaceDoc, patch: { category?: string; tags?: string[]; version?: string }) {
  try {
    await updateSpaceDoc(spaceId, d.id, patch)
    toastSuccess('已保存')
    await reloadDocs()
  } catch (e: any) {
    toastError(getErrorMessage(e, '保存失败'))
  }
}

async function toggleEnabled(d: SpaceDoc) {
  try {
    await updateSpaceDoc(spaceId, d.id, { is_enabled: !d.is_enabled })
    await reloadDocs()
  } catch (e: any) {
    toastError(getErrorMessage(e, '操作失败'))
  }
}

async function reindex(d: SpaceDoc) {
  try {
    await reindexSpaceDoc(spaceId, d.id)
    toastSuccess('已创建重建任务')
    await reloadDocs()
  } catch (e: any) {
    toastError(getErrorMessage(e, '重建失败'))
  }
}

async function removeDoc(d: SpaceDoc) {
  if (!window.confirm(`删除「${d.file_name}」？片段和向量数据也会删除。`)) return
  try {
    await deleteSpaceDoc(spaceId, d.id)
    toastSuccess('已删除')
    await Promise.all([reloadSpace(), reloadDocs()])
  } catch (e: any) {
    toastError(getErrorMessage(e, '删除失败'))
  }
}

onMounted(async () => {
  await Promise.all([reloadSpace(), reloadDocs()])
})
</script>
