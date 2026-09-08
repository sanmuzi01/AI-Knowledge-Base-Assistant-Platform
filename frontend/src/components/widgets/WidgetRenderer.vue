<template>
  <component :is="viewComponent" :widget="widget" :result="result" :error="error" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetItem } from '../../api/widget'
import { resolveWidgetView } from './registry'

const props = defineProps<{ widget: WidgetItem }>()

// 统一渲染器：只按 view.kind 从注册表取组件，不写 if/else 链
const viewComponent = computed(() => resolveWidgetView(props.widget.view_kind))

const result = computed(() => props.widget.latest?.payload?.result ?? null)
const error = computed(() =>
  props.widget.latest && !props.widget.latest.ok ? props.widget.latest.error || '这次没取到数据' : '',
)
</script>
