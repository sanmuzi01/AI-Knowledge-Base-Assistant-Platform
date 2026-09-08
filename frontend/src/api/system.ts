import request from '../utils/request'

export interface HealthCheckItem {
  name: string
  ok: boolean
  message: string
}

export interface HealthStatus {
  ok: boolean
  checks: HealthCheckItem[]
  cache?: {
    config?: {
      backend?: string
      redis_ok?: boolean
      size: number
      memory_size?: number
      redis_size?: number
      expired_removed: number
    }
    skill?: {
      backend?: string
      redis_ok?: boolean
      size: number
      memory_size?: number
      redis_size?: number
      expired_removed: number
    }
    verification?: {
      backend?: string
      redis_ok?: boolean
      size: number
      memory_size?: number
      redis_size?: number
      expired_removed: number
    }
  }
  limits?: {
    rate?: {
      backend?: string
      redis_ok?: boolean
      memory_size?: number
    }
    concurrency?: {
      backend?: string
      redis_ok?: boolean
      memory_active?: number
    }
  }
  tasks?: {
    execution_mode?: string
    worker_required?: boolean
    running_timeout_seconds?: number
    max_auto_retries?: number
    retry_base_seconds?: number
    retry_max_seconds?: number
  }
  database?: {
    pool?: Record<string, number | null>
  }
  config?: {
    environment?: string
    ok?: boolean
    error_count?: number
    warning_count?: number
    checks?: Array<HealthCheckItem & { level?: string }>
  }
  resilience?: {
    circuits?: Record<string, unknown>
  }
}

export async function getHealth(): Promise<HealthStatus> {
  const { data } = await request.get('/health')
  return data as HealthStatus
}
