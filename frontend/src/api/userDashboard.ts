import request from '../utils/request'

export type DashboardLevel = 'danger' | 'warn' | 'info'

export interface DashboardCounts {
  agents: number
  ready_agents: number
  llm_configs: number
  chat_models: number
  embedding_models: number
  skills: number
  knowledge_docs: number
  knowledge_done: number
  conversations: number
  messages: number
  runs: number
  tasks: number
  memories: number
  tokens: number
}

export interface DashboardRecommendation {
  key: string
  level: DashboardLevel
  title: string
  description: string
  action_path: string
  action_text: string
}

export interface DashboardRun {
  id: number
  agent_id: number
  agent_name: string
  status: string
  question: string
  answer_preview: string
  total_steps: number
  total_tokens: number
  started_at?: string | null
  finished_at?: string | null
}

export interface DashboardTask {
  id: number
  agent_id?: number | null
  task_type: string
  title: string
  status: string
  progress: number
  error_msg?: string | null
  created_at?: string | null
}

export interface UserDashboard {
  counts: DashboardCounts
  status: {
    runs: Record<string, number>
    tasks: Record<string, number>
    knowledge: Record<string, number>
    profile_ready: boolean
    health_score: number
  }
  recent_runs: DashboardRun[]
  recent_tasks: DashboardTask[]
  recommendations: DashboardRecommendation[]
}

export async function getUserDashboard(): Promise<UserDashboard> {
  const { data } = await request.get<UserDashboard>('/user/dashboard')
  return data
}

export interface UserQuotaStatus {
  plan_id: number | null
  plan_name: string | null
  plan_display_name: string
  monthly_token_limit: number
  used_tokens: number
  remaining_tokens: number | null
  unlimited: boolean
  period_start: string
}

export async function getUserQuota(): Promise<UserQuotaStatus> {
  const { data } = await request.get<UserQuotaStatus>('/user/quota')
  return data
}
