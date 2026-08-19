import request from '../utils/request'

export interface AdminOverview {
  counts: Record<string, number>
  task_status: Record<string, number>
  knowledge_status: Record<string, number>
}

export interface AdminUser {
  id: number
  name: string
  age?: number | null
  is_disabled?: number
  last_login_at?: string | null
  last_seen_at?: string | null
  is_online?: boolean
  selected_agent_id?: number | null
  roles: string[]
  is_admin: boolean
  agent_count: number
  skill_count: number
  knowledge_count: number
  task_count: number
  counts?: Record<string, number>
}

export interface AdminTask {
  id: number
  user_id: number
  agent_id?: number | null
  task_type: string
  status: string
  title: string
  target_type?: string | null
  target_id?: number | null
  progress: number
  error_msg?: string | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export async function getAdminOverview(): Promise<AdminOverview> {
  const { data } = await request.get('/admin/overview')
  return data as AdminOverview
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  const { data } = await request.get('/admin/users')
  return data as AdminUser[]
}

export async function updateUserRoles(userId: number, roles: string[]) {
  const { data } = await request.put(`/admin/users/${userId}/roles`, { roles })
  return data
}

export async function getAdminUser(userId: number): Promise<AdminUser> {
  const { data } = await request.get(`/admin/users/${userId}`)
  return data as AdminUser
}

export async function updateUserStatus(userId: number, disabled: boolean) {
  const { data } = await request.patch(`/admin/users/${userId}/status`, { disabled })
  return data
}

export async function resetUserPassword(userId: number, newPassword: string) {
  const { data } = await request.put(`/admin/users/${userId}/password`, { new_password: newPassword })
  return data
}

export async function deleteAdminUser(userId: number) {
  const { data } = await request.delete(`/admin/users/${userId}`)
  return data
}

export async function listAdminTasks(limit = 50): Promise<AdminTask[]> {
  const { data } = await request.get('/admin/tasks', { params: { limit } })
  return data as AdminTask[]
}
