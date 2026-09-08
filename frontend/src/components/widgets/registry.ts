import type { Component } from 'vue'
import ChartWidget from './ChartWidget.vue'
import MetricWidget from './MetricWidget.vue'
import MarkdownWidget from './MarkdownWidget.vue'
import TableWidget from './TableWidget.vue'
import WebMonitorWidget from './WebMonitorWidget.vue'
import TaskListWidget from './TaskListWidget.vue'
import SystemStatsWidget from './SystemStatsWidget.vue'
import FallbackWidget from './FallbackWidget.vue'

/**
 * 视图注册表：view.kind -> 渲染组件。
 * 新增一种展示形态时，写一个组件并在这里加一行，WidgetRenderer 不用改。
 */
export const viewRegistry: Record<string, Component> = {
  chart: ChartWidget,
  metric: MetricWidget,
  markdown: MarkdownWidget,
  table: TableWidget,
  web_monitor: WebMonitorWidget,
  task_list: TaskListWidget,
  system_stats: SystemStatsWidget,
}

export function resolveWidgetView(kind: string | undefined | null): Component {
  return viewRegistry[kind || ''] || FallbackWidget
}
