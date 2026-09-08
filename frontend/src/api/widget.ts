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

export async function designWidget(prompt: string): Promise<DesignResponse> {
  const { data } = await request.post<DesignResponse>('/user/widgets/design', { prompt })
  return data
}

export async function createWidget(draft: any): Promise<WidgetItem> {
  const { data } = await request.post<WidgetItem>('/user/widgets', { draft })
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

export async function getWidgetData(id: number, withSeries = false): Promise<{ widget: WidgetItem; series?: any[] }> {
  const { data } = await request.get(`/user/widgets/${id}/data`, { params: { with_series: withSeries } })
  return data
}
