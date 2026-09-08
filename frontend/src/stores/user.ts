import { defineStore } from 'pinia'
import request from '../utils/request'

export interface User {
  id: number
  name: string
  selected_agent_id?: number | null
  selected_agent?: any
  roles?: string[]
  is_admin?: boolean
}

const USER_KEY = 'user'
const TOKEN_KEY = 'token'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null') as User | null,
  }),
  actions: {
    async login(name: string, password: string) {
      const { data } = await request.post('/user/login', { name, password })
      // 后端返回：{ access_token, token_type, user_id, username, message }
      const token: string = data.access_token || data.token
      if (!token) {
        throw new Error(data.message || '登录失败')
      }
      const user: User = {
        id: data.user_id,
        name: data.username || data.user?.name || name,
        selected_agent_id: data.selected_agent_id ?? data.user?.selected_agent_id ?? null,
        roles: data.roles || [],
        is_admin: Boolean(data.is_admin),
      }
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      return { token, user }
    },
    async refreshMe() {
      if (!this.token) return null
      const { data } = await request.get('/user/me')
      const user: User = {
        id: data.user_id,
        name: data.username,
        selected_agent_id: data.selected_agent_id ?? null,
        roles: data.roles || [],
        is_admin: Boolean(data.is_admin),
      }
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      return user
    },
    async sendRegisterSmsCode(phone: string) {
      const { data } = await request.post('/user/register/sms-code', { phone })
      return data
    },
    async register(name: string, password: string, age: number, phone: string, smsCode: string, acceptedTerms: boolean) {
      const { data } = await request.post('/user/register', {
        name,
        password,
        age,
        phone,
        sms_code: smsCode,
        accepted_terms: acceptedTerms,
      })
      return data
    },
    async changePassword(oldPassword: string, newPassword: string) {
      const { data } = await request.post('/user/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      return data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (location.pathname !== '/login') {
        location.href = '/login'
      }
    },
  },
})
