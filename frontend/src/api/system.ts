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
      size: number
      expired_removed: number
    }
    skill?: {
      size: number
      expired_removed: number
    }
  }
}

export async function getHealth(): Promise<HealthStatus> {
  const { data } = await request.get('/health')
  return data as HealthStatus
}
