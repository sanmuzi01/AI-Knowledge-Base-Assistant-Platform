import request from '../utils/request'

export interface WebMonitor {
  id: number
  agent_id?: number | null
  name: string
  url: string
  interval_minutes: number
  is_active: boolean
  last_status: string
  last_title?: string | null
  last_excerpt?: string | null
  last_error?: string | null
  last_checked_at?: string | null
  last_change_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  changed?: boolean
}

export interface WebMonitorPayload {
  name?: string
  url: string
  interval_minutes?: number
  agent_id?: number | null
}

export async function listWebMonitors(): Promise<WebMonitor[]> {
  const { data } = await request.get<WebMonitor[]>('/web-monitor')
  return data
}

export async function createWebMonitor(payload: WebMonitorPayload): Promise<WebMonitor> {
  const { data } = await request.post<WebMonitor>('/web-monitor', payload)
  return data
}

export async function updateWebMonitor(id: number, payload: Partial<WebMonitorPayload> & { is_active?: boolean }): Promise<WebMonitor> {
  const { data } = await request.patch<WebMonitor>(`/web-monitor/${id}`, payload)
  return data
}

export async function checkWebMonitor(id: number): Promise<WebMonitor> {
  const { data } = await request.post<WebMonitor>(`/web-monitor/${id}/check`)
  return data
}

export async function deleteWebMonitor(id: number): Promise<void> {
  await request.delete(`/web-monitor/${id}`)
}
