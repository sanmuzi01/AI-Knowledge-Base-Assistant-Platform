import request from '../utils/request'

// 面向普通用户的四句话说明（前端只展示这些，不展示技术字段）
export interface WidgetFriendly {
  data_from: string
  system_does: string
  show_as: string
  update_every: string
}

export interface WidgetLatest {
  ok: boolean
  label: string | null
  value: number | null
  error: string | null
  payload: any
  recorded_at: string | null
}

export interface WidgetItem {
  id: number
  name: string
  type: string
  type_label: string
  description: string
  enabled: boolean
  sort_order: number
  spec_version: number
  view_kind: string
  view: { kind: string; config: Record<string, any> }
  actions: string[]
  friendly: WidgetFriendly
  config: Record<string, any>
  attention: 'alert' | 'warn' | 'changed' | null
  status: {
    last_run_at: string | null
    last_status: string | null
    fail_count: number
    next_run_at: string | null
  }
  latest: WidgetLatest | null
}

export interface WidgetCatalog {
  spec_version: number
  widget_types: { key: string; label: string }[]
  views: { key: string; label: string }[]
  triggers: { key: string; label: string }[]
  actions: { key: string; label: string }[]
  data_sources: { key: string; label: string }[]
  catalog_providers: { key: string; label: string }[]
}

export interface WidgetListResponse {
  items: WidgetItem[]
  catalog: WidgetCatalog
}

export interface DesignResponse {
  needs_clarification: boolean
  message?: string
  reason?: string
  draft?: any
  explain?: WidgetFriendly
}

export interface PreviewResponse {
  ok: boolean
  message: string
  explain?: WidgetFriendly
  view: { kind: string; config: Record<string, any> }
  view_kind: string
  data: any
  label?: string | null
  value?: number | null
}

export interface WidgetSeriesPoint {
  recorded_at: string | null
  ok: boolean
  label: string | null
  value: number | null
}

export interface TemplateField {
  name: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'url' | 'time' | 'select' | 'agent' | 'space'
  required: boolean
  placeholder?: string
  help?: string
  default?: any
  options?: { value: string; label: string }[]
  show_if?: { field: string; eq?: string; in?: string[] }
  min?: number
  max?: number
}

export interface WidgetTemplate {
  key: string
  name: string
  icon: string
  description: string
  tags: string[]
  experimental: boolean
  fields: TemplateField[]
}

export interface TemplateCatalog {
  templates: WidgetTemplate[]
  options: {
    agents: { value: number; label: string }[]
    spaces: { value: number; label: string }[]
  }
}

export async function listWidgetTemplates(): Promise<TemplateCatalog> {
  const { data } = await request.get<TemplateCatalog>('/user/widgets/templates')
  return data
}

export async function buildWidgetFromTemplate(
  templateKey: string,
  params: Record<string, any>,
): Promise<{ draft: any; explain: WidgetFriendly }> {
  const { data } = await request.post('/user/widgets/from-template', {
    template_key: templateKey,
    params,
  })
  return data
}

export async function designWidget(prompt: string): Promise<DesignResponse> {
  const { data } = await request.post<DesignResponse>('/user/widgets/design', { prompt })
  return data
}

export async function createWidget(draft: any): Promise<WidgetItem> {
  const { data } = await request.post<WidgetItem>('/user/widgets', { draft })
  return data
}

export async function previewWidget(draft: any): Promise<PreviewResponse> {
  const { data } = await request.post<PreviewResponse>('/user/widgets/preview', { draft })
  return data
}

export async function listWidgets(): Promise<WidgetListResponse> {
  const { data } = await request.get<WidgetListResponse>('/user/widgets')
  return data
}

export async function updateWidget(
  id: number,
  patch: { name?: string; description?: string; enabled?: boolean; sort_order?: number; spec?: any },
): Promise<WidgetItem> {
  const { data } = await request.patch<WidgetItem>(`/user/widgets/${id}`, patch)
  return data
}

export async function deleteWidget(id: number): Promise<{ message: string; id: number }> {
  const { data } = await request.delete(`/user/widgets/${id}`)
  return data
}

export async function runWidget(id: number): Promise<{ ok: boolean; message: string; data: any; label?: string; value?: number }> {
  const { data } = await request.post(`/user/widgets/${id}/run`)
  return data
}

export async function getWidgetData(
  id: number,
  withSeries = false,
): Promise<{ widget: WidgetItem; series?: WidgetSeriesPoint[] }> {
  const { data } = await request.get(`/user/widgets/${id}/data`, { params: { with_series: withSeries } })
  return data
}

export async function exportWidget(id: number): Promise<any> {
  const { data } = await request.get(`/user/widgets/${id}/export`)
  return data
}

export async function importWidget(payload: any): Promise<WidgetItem> {
  const { data } = await request.post<WidgetItem>('/user/widgets/import', { payload })
  return data
}
