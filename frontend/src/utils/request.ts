import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { toastError } from './toast'

export const getErrorMessage = (err: any, fallback = '请求失败') => {
  const detail = err?.response?.data?.detail || err?.response?.data?.message
  if (detail) return detail
  if (err?.code === 'ECONNABORTED') return '请求超时，请稍后重试或检查后端任务是否仍在处理'
  if (!err?.response && (err?.message === 'Network Error' || err?.code === 'ERR_NETWORK')) {
    return '无法连接后端服务，请确认后端已启动并监听 127.0.0.1:8000'
  }
  return err?.message || fallback
}

// Axios 单例：统一前缀 /api（匹配 vite.config.ts 的代理）、JWT 注入、401 清理
const request: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 300_000, // 5 分钟，同步对话 + RAG 切分可能很慢
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (resp: AxiosResponse) => resp,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (location.pathname !== '/login') {
        location.href = '/login'
      }
    } else {
      toastError(getErrorMessage(err))
    }
    return Promise.reject(err)
  },
)

export default request
