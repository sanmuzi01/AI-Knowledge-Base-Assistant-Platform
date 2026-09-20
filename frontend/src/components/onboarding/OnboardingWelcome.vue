<template>
  <div
    class="fixed inset-0 z-[70] flex items-start justify-center overflow-y-auto px-5 py-10 sm:items-center"
    style="background: radial-gradient(60% 55% at 0% 100%, var(--tint-1), transparent 70%), radial-gradient(50% 45% at 100% 0%, var(--tint-2), transparent 70%), var(--bg)"
  >
    <button
      type="button"
      class="absolute right-5 top-5 text-[14px] text-slate-500 hover:text-slate-900"
      @click="$emit('skip')"
    >
      跳过
    </button>

    <div class="mx-auto w-full max-w-[640px] text-center">
      <span
        class="ob-rise mx-auto flex h-[84px] w-[84px] items-center justify-center rounded-[24px] bg-gradient-to-b from-[#3d3d40] to-[#0e0e10] text-white shadow-[inset_0_1px_0_rgba(255,255,255,.26),0_10px_28px_rgba(0,0,0,.24),0_1px_3px_rgba(0,0,0,.3)]"
      >
        <Sparkles :size="40" :stroke-width="1.6" />
      </span>
      <h1 class="ob-rise mt-7 text-[clamp(28px,6vw,42px)] font-semibold leading-tight tracking-[-0.032em] [animation-delay:80ms] [text-wrap:balance]">
        欢迎，{{ name }}
      </h1>
      <p class="ob-rise mx-auto mt-3 max-w-[460px] text-[16px] leading-7 text-slate-500 [animation-delay:150ms]">
        这里是你的私人 AI 助手工作台。跟着下面 4 步走，几分钟内就能让第一个助手开口说话。
      </p>

      <ol class="mt-9 grid gap-3 text-left sm:grid-cols-2">
        <li
          v-for="(step, i) in steps"
          :key="step.key"
          class="ob-rise ui-card flex items-start gap-3.5 p-4"
          :style="{ animationDelay: `${240 + i * 80}ms` }"
        >
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[14px] font-semibold text-[var(--accent)]">
            {{ i + 1 }}
          </span>
          <div class="min-w-0">
            <p class="text-[15px] font-semibold tracking-[-0.012em] text-slate-900">{{ step.title }}</p>
            <p class="mt-0.5 text-[12.5px] text-slate-400">{{ step.minutes }}</p>
          </div>
        </li>
      </ol>

      <div class="ob-rise mt-9 flex flex-col items-center gap-3.5 [animation-delay:600ms]">
        <button
          type="button"
          class="ui-primary inline-flex h-12 min-w-[220px] items-center justify-center gap-2 px-8 text-[16px] font-medium tracking-[-0.01em]"
          @click="$emit('start')"
        >
          开始设置
          <ArrowRight :size="18" :stroke-width="2" />
        </button>
        <button type="button" class="text-[14px] text-slate-500 hover:text-slate-900" @click="$emit('skip')">
          我先自己看看
        </button>
        <p class="mt-1 text-[12px] text-slate-400">随时可以在侧栏「更多 → 新手指引」重新打开。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, Sparkles } from 'lucide-vue-next'
import { ONBOARDING_STEPS } from '../../stores/onboarding'

defineProps<{ name: string }>()
defineEmits<{ start: []; skip: [] }>()

const steps = ONBOARDING_STEPS
</script>
