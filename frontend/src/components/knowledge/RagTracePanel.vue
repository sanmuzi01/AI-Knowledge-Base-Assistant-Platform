<template>
  <div v-if="trace" class="space-y-4">
    <!-- 概览 -->
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span class="rounded bg-slate-100 px-2 py-0.5 text-slate-600">模式：{{ modeLabel }}</span>
      <span class="rounded bg-slate-100 px-2 py-0.5 text-slate-600">命中 {{ trace.hit_count }} 条</span>
      <span class="rounded bg-slate-100 px-2 py-0.5 text-slate-600">top_k {{ trace.top_k }}</span>
      <span v-if="trace.rerank" class="rounded bg-violet-50 px-2 py-0.5 text-violet-700">已重排</span>
      <span v-if="trace.refused" class="rounded bg-amber-50 px-2 py-0.5 text-amber-700">按「查不到」处理</span>
    </div>

    <!-- 上下文压缩 / Token 节省 -->
    <RagSavingsBar :stats="trace.stats" />

    <!-- 命中片段 -->
    <section>
      <h4 class="mb-1 text-xs font-semibold text-slate-700">命中片段</h4>
      <div v-if="trace.hits.length === 0" class="rounded border border-slate-200 bg-slate-50 px-3 py-4 text-center text-xs text-slate-400">
        没有命中任何片段
      </div>
      <ol v-else class="space-y-2">
        <li v-for="(h, i) in trace.hits" :key="i" class="rounded border border-slate-200 bg-white p-3 text-xs">
          <div class="mb-1 flex flex-wrap items-center gap-2 text-slate-500">
            <span class="font-medium text-slate-700">{{ h.source.space_name }} / {{ h.source.file_name }}</span>
            <span v-if="h.source.version" class="rounded bg-slate-100 px-1.5">{{ h.source.version }}</span>
            <span v-if="h.source.category" class="rounded bg-slate-100 px-1.5">{{ h.source.category }}</span>
            <span class="ml-auto">分数 {{ fmt(h.score) }}</span>
            <span v-if="h.rerank_score != null">rerank {{ fmt(h.rerank_score) }}</span>
          </div>
          <p class="whitespace-pre-wrap leading-relaxed text-slate-700">{{ short(h.content, 400) }}</p>
        </li>
      </ol>
    </section>

    <!-- 最终上下文（折叠） -->
    <section v-if="trace.context">
      <button class="text-xs font-semibold text-slate-600 hover:text-slate-900" @click="showContext = !showContext">
        {{ showContext ? '▾' : '▸' }} 最终上下文（喂给模型的内容）
      </button>
      <pre v-if="showContext" class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">{{ trace.context }}</pre>
    </section>

    <!-- 模型回答 -->
    <section v-if="trace.answer || trace.answer_error">
      <h4 class="mb-1 text-xs font-semibold text-slate-700">模型回答</h4>
      <p v-if="trace.answer_error" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        生成失败：{{ trace.answer_error }}
      </p>
      <div v-else class="rounded border border-slate-200 bg-white p-3 text-xs leading-relaxed whitespace-pre-wrap text-slate-800">
        {{ trace.answer }}
      </div>
      <div v-if="trace.faithfulness && trace.faithfulness.score != null" class="mt-1 text-[11px] text-slate-500">
        忠诚度（启发式）：{{ Math.round(trace.faithfulness.score * 100) }}%
        （{{ trace.faithfulness.supported_claims }}/{{ trace.faithfulness.claim_count }} 条陈述有资料支撑）
      </div>
    </section>

    <!-- 引用来源 -->
    <section v-if="trace.citations.length">
      <h4 class="mb-1 text-xs font-semibold text-slate-700">引用来源</h4>
      <div class="flex flex-wrap gap-1.5">
        <span v-for="c in trace.citations" :key="c.index"
          class="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600">
          【来源{{ c.index }}】{{ c.file_name }}
        </span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RagDebugTrace } from '../../api/ragDebug'
import RagSavingsBar from './RagSavingsBar.vue'

const props = defineProps<{ trace: RagDebugTrace | null }>()
const showContext = ref(false)

const modeLabel = computed(() =>
  props.trace?.mode === 'spaces' ? '多空间联合检索'
    : props.trace?.mode === 'agent' ? '本助手私有库' : (props.trace?.mode || '-'))

const fmt = (n: number | null) => (n == null ? '-' : n.toFixed(3))
const short = (t: string, n: number) => (t && t.length > n ? t.slice(0, n) + '…' : t || '')
</script>
