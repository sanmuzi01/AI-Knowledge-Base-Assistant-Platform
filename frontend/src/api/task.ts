import request from '../utils/request'

/** 后台任务状态 */
export type TaskStatus = 'queued' | 'running' | 'finished' | 'failed' | 'cancelled'

/** 后台任务（对应后端 task_to_dict） */
export interface Task {
  id: number
  user_id: number
  agent_id: number | null
  task_type: string
  status: TaskStatus
  title: string
  target_type: string | null
  target_id: number | null
  progress: number
  result: any
  error_msg: string | null
  retry_count: number
  parent_task_id: number | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  next_run_at: string | null
}

/** 兼容旧名（Knowledge.vue 等在用） */
export type BackgroundTask = Task

/** retry/cancel 接口的后端包装 */
interface TaskActionResponse {
  code: number
  msg: string
  data: Task
}

/** 查询参数 */
export interface TaskQuery {
  limit?: number
  status?: TaskStatus
  task_type?: string
}

// ===== 查询 =====

/** 查询当前用户的后台任务（支持筛选）
 *  两种调用方式：listTasks(20) 取前 20 条；listTasks({ status: 'failed', limit: 50 }) 带筛选
 */
export async function listTasks(limit: number): Promise<Task[]>
export async function listTasks(params?: TaskQuery): Promise<Task[]>
export async function listTasks(arg: number | TaskQuery = {}): Promise<Task[]> {
  const params = typeof arg === 'number' ? { limit: arg } : arg
  const { data } = await request.get<Task[]>('/task/', { params })
  return data
}

/** 管理员查询全局后台任务（支持筛选） */
export async function listAllTasks(params: TaskQuery = {}): Promise<Task[]> {
  const { data } = await request.get<Task[]>('/task/all', { params })
  return data
}

// ===== 操作 =====

/** 重试任务（仅 failed/cancelled 可重试，后端会创建新任务并用 BackgroundTasks 触发执行） */
export async function retryTask(taskId: number): Promise<Task> {
  const { data } = await request.post<TaskActionResponse>(`/task/${taskId}/retry`)
  return data.data
}

/** 取消任务（仅 queued 可取消；running 无法中断） */
export async function cancelTask(taskId: number): Promise<Task> {
  const { data } = await request.post<TaskActionResponse>(`/task/${taskId}/cancel`)
  return data.data
}
