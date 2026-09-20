<template>
  <div class="flex h-screen flex-col bg-transparent text-slate-950">
    <header class="border-b border-sky-200/70 bg-white/80 px-5 py-4 shadow-sm backdrop-blur-xl lg:px-8">
      <div class="mx-auto flex max-w-5xl items-center gap-3">
        <button
          @click="router.push(`/knowledge-spaces/${spaceId}`)"
          class="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-500 hover:bg-black/[.06] hover:text-slate-900"
          title="返回空间详情"
        >
          <ArrowLeft :size="16" />
        </button>
        <div>
          <h1 class="text-xl font-semibold">知识库健康报告</h1>
          <p class="mt-0.5 text-sm text-slate-500">{{ space?.name || '知识库空间' }}</p>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-5xl flex-1 space-y-5 overflow-y-auto p-5 lg:p-8">
      <div v-if="loading" class="py-16 text-center text-sm text-slate-400">计算中…</div>
      <div v-else-if="loadErr" class="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ loadErr }}</div>

      <template v-else-if="health">
        <!-- 总分 -->
        <section class="flex items-center gap-6 rounded-lg border border-sky-200 bg-white/80 p-5">
          <div class="text-center">
            <div class="text-4xl font-bold" :class="levelColor">{{ health.health_score }}</div>
            <div class="text-xs text-slate-400">满分 100</div>
          </div>
          <div class="flex-1">
            <span class="rounded px-2 py-0.5 text-xs font-medium" :class="levelBadge">{{ levelLabel }}</span>
            <p class="mt-2 text-xs text-slate-500">
              {{ health.documents.total }} 份文档 · {{ health.documents.chunk_count }} 个片段 ·
              {{ health.retrieval.sample_count }} 条调试样例 ·
              久未更新阈值 {{ health.stale_days }} 天
            </p>
          </div>
          <button @click="load" class="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
            重新计算
          </button>
        </section>

        <!-- 文档侧 -->
        <section class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <h3 class="mb-3 text-sm font-semibold text-slate-800">文档质量</h3>
          <div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Metric label="已入库" :value="health.documents.done" :total="health.documents.total" />
            <Metric label="入库失败" :value="health.documents.failed" :rate="health.documents.failed_rate" bad />
            <Metric label="待入库" :value="health.documents.pending" :rate="health.documents.pending_rate" />
            <Metric label="久未更新" :value="health.documents.stale" :rate="health.documents.stale_rate" bad />
            <Metric label="切片为空" :value="health.documents.empty_done" bad />
            <Metric label="已禁用" :value="health.documents.total - health.documents.enabled" :rate="health.documents.disabled_rate" />
          </div>
        </section>

        <!-- 检索侧 -->
        <section class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <h3 class="mb-1 text-sm font-semibold text-slate-800">检索质量（来自调试台样例）</h3>
          <p v-if="health.retrieval.sample_count < 3" class="mb-3 text-xs text-amber-600">
            样例不足 3 条，检索质量指标仅供参考，也不计入健康分。去调试台多存几条。
          </p>
          <div class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Metric label="命中率" :rate="health.retrieval.hit_rate" />
            <Metric label="拒答率" :rate="health.retrieval.refuse_rate" bad />
            <Metric label="引用率" :rate="health.retrieval.citation_rate" />
            <Metric label="人工好评率" :rate="health.retrieval.useful_rate" />
          </div>
        </section>

        <!-- 跑评估（一次性，不留痕迹） -->
        <section class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-800">按评估集跑一次 RAG 评估</h3>
            <div class="flex gap-2">
              <button
                @click="saveAsFixedSet" :disabled="evalRunning || savingSet"
                class="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >{{ savingSet ? '保存中…' : '存成固定评估集' }}</button>
              <button
                @click="runEval" :disabled="evalRunning"
                class="ui-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
              >{{ evalRunning ? '评估中…' : '跑一次' }}</button>
            </div>
          </div>
          <p class="text-xs text-slate-500">
            用调试台里勾进「评估集」的样例，走多空间联合检索算命中率 / 召回 / 忠诚度。
            "跑一次"是一次性的，不会留痕迹；"存成固定评估集"之后可以重复跑、自动跟上一轮比较有没有变差。
          </p>
          <p v-if="evalMsg" class="mt-2 text-xs" :class="evalErr ? 'text-red-600' : 'text-slate-500'">{{ evalMsg }}</p>
          <div v-if="report" class="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
            <Metric label="用例数" :value="report.case_count" />
            <Metric label="命中率" :rate="report.metrics.hit_rate" />
            <Metric label="召回" :rate="report.metrics.recall" />
            <Metric label="precision@k" :rate="report.metrics.precision_at_k" />
            <Metric label="忠诚度" :rate="report.metrics.faithfulness" />
          </div>
        </section>

        <!-- 固定评估集：可重复跑，自动跟上一轮比较 -->
        <section class="rounded-lg border border-sky-200 bg-white/80 p-4">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-800">固定评估集</h3>
            <button @click="loadEvalSets" class="rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50">刷新</button>
          </div>
          <div v-if="evalSets.length === 0"
               class="rounded border border-dashed border-slate-200 bg-slate-50 px-3 py-6 text-center text-xs text-slate-400">
            还没有固定评估集。用上面的"存成固定评估集"从调试台样例建一份。
          </div>
          <div v-else class="space-y-2">
            <div v-for="s in evalSets" :key="s.id" class="rounded border border-slate-200 bg-white px-3 py-2.5">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-slate-800">{{ s.name }}</p>
                  <p class="text-xs text-slate-400">{{ s.cases.length }} 条用例</p>
                </div>
                <div class="flex shrink-0 gap-1.5">
                  <button
                    @click="runFixedSet(s)" :disabled="runningSetId === s.id"
                    class="ui-primary rounded px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
                  >{{ runningSetId === s.id ? '跑一次…' : '重新跑一次' }}</button>
                  <button
                    @click="removeEvalSet(s)" :disabled="runningSetId === s.id"
                    class="rounded border border-red-200 px-2.5 py-1.5 text-xs text-red-700 hover:bg-red-50 disabled:opacity-40"
                  >删除</button>
                </div>
              </div>
              <div v-if="runResults[s.id]" class="mt-2 border-t border-slate-100 pt-2">
                <div class="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
                  <Metric label="命中率" :rate="runResults[s.id].report.metrics.hit_rate" />
                  <Metric label="召回" :rate="runResults[s.id].report.metrics.recall" />
                  <Metric label="precision@k" :rate="runResults[s.id].report.metrics.precision_at_k" />
                  <Metric label="忠诚度" :rate="runResults[s.id].report.metrics.faithfulness" />
                </div>
                <div v-if="runResults[s.id].diff" class="mt-2 space-y-1 text-xs">
                  <p v-if="runResults[s.id].diff!.regressed_questions.length" class="text-red-600">
                    ⚠ 回归了 {{ runResults[s.id].diff!.regressed_questions.length }} 条：{{ runResults[s.id].diff!.regressed_questions.join('、') }}
                  </p>
                  <p v-if="runResults[s.id].diff!.improved_questions.length" class="text-emerald-600">
                    ✓ 变好了 {{ runResults[s.id].diff!.improved_questions.length }} 条：{{ runResults[s.id].diff!.improved_questions.join('、') }}
                  </p>
                  <p v-if="!runResults[s.id].diff!.regressed_questions.length && !runResults[s.id].diff!.improved_questions.length" class="text-slate-400">
                    和上一轮相比没有变化
                  </p>
                </div>
                <p v-else class="mt-2 text-xs text-slate-400">第一次运行，没有上一轮可比较</p>
              </div>
            </div>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref, type FunctionalComponent } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import * as ksApi from '../../api/knowledgeSpace'
import type { KnowledgeSpace, SpaceHealth } from '../../api/knowledgeSpace'
import { exportRagEvalCases } from '../../api/ragDebug'
import { evaluateSpaceRag, createEvalSet, deleteEvalSet, listEvalSets, runEvalSet } from '../../api/evaluation'
import type { RagEvalReport, EvalSet, EvalRunResult } from '../../api/evaluation'
import { getErrorMessage } from '../../utils/request'

const props = defineProps<{ id: string | number }>()
const router = useRouter()
const spaceId = computed(() => Number(props.id))

const space = ref<KnowledgeSpace | null>(null)
const health = ref<SpaceHealth | null>(null)
const loading = ref(true)
const loadErr = ref('')

const evalRunning = ref(false)
const evalMsg = ref('')
const evalErr = ref(false)
const report = ref<RagEvalReport | null>(null)
const savingSet = ref(false)

const evalSets = ref<EvalSet[]>([])
const runningSetId = ref<number | null>(null)
const runResults = ref<Record<number, EvalRunResult>>({})

const levelLabel = computed(() =>
  health.value?.level === 'good' ? '健康' : health.value?.level === 'fair' ? '一般' : '需要关注')
const levelColor = computed(() =>
  health.value?.level === 'good' ? 'text-emerald-600' : health.value?.level === 'fair' ? 'text-amber-600' : 'text-red-600')
const levelBadge = computed(() =>
  health.value?.level === 'good' ? 'bg-emerald-50 text-emerald-700'
    : health.value?.level === 'fair' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700')

const load = async () => {
  loading.value = true
  loadErr.value = ''
  try {
    if (!space.value) space.value = await ksApi.getSpace(spaceId.value)
    health.value = await ksApi.getSpaceHealth(spaceId.value)
  } catch (e: any) {
    loadErr.value = getErrorMessage(e, '加载健康报告失败')
  } finally {
    loading.value = false
  }
}

const runEval = async () => {
  evalRunning.value = true
  evalMsg.value = ''
  evalErr.value = false
  report.value = null
  try {
    const { cases } = await exportRagEvalCases({ space_id: spaceId.value })
    if (!cases.length) {
      evalMsg.value = '评估集为空，请先在调试台把样例勾进「评估集」'
      return
    }
    report.value = await evaluateSpaceRag(spaceId.value, { cases, top_k: 5 })
    evalMsg.value = `已用 ${cases.length} 条评估用例跑完`
  } catch (e: any) {
    evalErr.value = true
    evalMsg.value = getErrorMessage(e, '评估失败')
  } finally {
    evalRunning.value = false
  }
}

const saveAsFixedSet = async () => {
  const name = prompt('给这份评估集起个名字（比如"客服常见问题-v1"）')
  if (!name || !name.trim()) return
  savingSet.value = true
  evalMsg.value = ''
  evalErr.value = false
  try {
    const { cases } = await exportRagEvalCases({ space_id: spaceId.value })
    if (!cases.length) {
      evalMsg.value = '评估集为空，请先在调试台把样例勾进「评估集」'
      evalErr.value = true
      return
    }
    await createEvalSet({ name: name.trim(), space_id: spaceId.value, cases, top_k: 5 })
    evalMsg.value = `已保存「${name.trim()}」，共 ${cases.length} 条用例`
    await loadEvalSets()
  } catch (e: any) {
    evalErr.value = true
    evalMsg.value = getErrorMessage(e, '保存失败')
  } finally {
    savingSet.value = false
  }
}

const loadEvalSets = async () => {
  try {
    evalSets.value = await listEvalSets({ space_id: spaceId.value })
  } catch {
    evalSets.value = []
  }
}

const runFixedSet = async (s: EvalSet) => {
  runningSetId.value = s.id
  try {
    const result = await runEvalSet(s.id)
    runResults.value = { ...runResults.value, [s.id]: result }
  } catch (e: any) {
    evalErr.value = true
    evalMsg.value = getErrorMessage(e, '运行失败')
  } finally {
    runningSetId.value = null
  }
}

const removeEvalSet = async (s: EvalSet) => {
  if (!confirm(`确认删除固定评估集「${s.name}」？历史运行记录也会一并删除。`)) return
  try {
    await deleteEvalSet(s.id)
    await loadEvalSets()
  } catch (e: any) {
    evalErr.value = true
    evalMsg.value = getErrorMessage(e, '删除失败')
  }
}

const Metric: FunctionalComponent<{ label: string; value?: number; rate?: number | null; total?: number; bad?: boolean }> =
  (p) => {
    const parts: any[] = []
    if (p.value != null) parts.push(h('span', { class: 'text-lg font-semibold' }, String(p.value)))
    if (p.rate != null) parts.push(h('span', { class: 'text-lg font-semibold' }, `${Math.round(p.rate * 100)}%`))
    if (p.rate == null && p.value == null) parts.push(h('span', { class: 'text-lg font-semibold text-slate-300' }, '—'))
    if (p.total != null) parts.push(h('span', { class: 'ml-1 text-xs text-slate-400' }, `/ ${p.total}`))
    return h('div', { class: 'rounded border border-slate-200 bg-white px-3 py-2' }, [
      h('div', { class: p.bad ? 'text-slate-700' : 'text-slate-700' }, parts),
      h('div', { class: 'text-xs text-slate-400' }, p.label),
    ])
  }

onMounted(() => {
  load()
  loadEvalSets()
})
</script>
