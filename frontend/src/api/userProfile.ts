import request from '../utils/request'

export interface UserProfile {
  occupation: string
  skills: string
  preferences: string
  communication_style: string
  persona: string
  extra_info: string
  auto_summary?: string
  last_inferred_at?: string | null
  updated_at?: string | null
}

export const defaultProfile: UserProfile = {
  occupation: '',
  skills: '',
  preferences: '',
  communication_style: 'balanced',
  persona: 'professional',
  extra_info: '',
  auto_summary: '',
  last_inferred_at: null,
  updated_at: null,
}

export const getUserProfile = async () => {
  const { data } = await request.get<UserProfile>('/user/profile')
  return data
}

export const saveUserProfile = async (payload: UserProfile) => {
  const { data } = await request.put<UserProfile>('/user/profile', payload)
  return data
}
