import request from '../utils/request'

export interface Skill {
  id: number
  user_id: number
  name: string
  description?: string
  config_file: string
  is_public: number
  created_at?: string
  config?: SkillConfig | null
}

export interface SkillTemplate {
  filename: string
  name: string
  description?: string
  tool_names?: string[]
  system_prompt?: string
  editable?: boolean
}

export interface SkillPermissions {
  network: boolean
  file_read: string[]
  exec: boolean
}

export interface SkillResource {
  name: string
  path: string
  exists: boolean
  size: number
  allowed: boolean
}

export interface SkillTool {
  name: string
  description: string
  parameters: Record<string, any>
  requires_context: boolean
  required_permissions?: Partial<SkillPermissions>
}

export interface SkillConfig {
  name: string
  description: string
  version: string
  tools: Array<{ name: string; defaults?: Record<string, any> }>
  tool_names: string[]
  system_prompt: string
  permissions: SkillPermissions
  resources: SkillResource[]
}

export interface SkillValidation {
  ok: boolean
  errors: string[]
  warnings: string[]
  tool_names: string[]
  missing_tool_names: string[]
  system_prompt_ready: boolean
  permissions: SkillPermissions
  resources: SkillResource[]
  resource_count: number
  allowed_resource_count: number
  skill_id: number
  name: string
  config_file: string
  is_public: number
}

/** 后端返回包装：{code, msg, data} */
interface SkillResponse<T> {
  code: number
  msg: string
  data: T
}

const encodeTemplatePath = (filename: string) => filename.split('/').map(encodeURIComponent).join('/')

// ===== 查询 =====
export async function listUserSkills(): Promise<Skill[]> {
  const { data } = await request.get<SkillResponse<Skill[]>>('/skill/')
  return data.data
}

export async function listPublicSkills(): Promise<Skill[]> {
  const { data } = await request.get<SkillResponse<Skill[]>>('/skill/public')
  return data.data
}

export async function getSkill(skillId: number): Promise<Skill> {
  const { data } = await request.get<SkillResponse<Skill>>(`/skill/${skillId}`)
  return data.data
}

export async function validateSkill(skillId: number): Promise<SkillValidation> {
  const { data } = await request.get<SkillResponse<SkillValidation>>(`/skill/${skillId}/validate`)
  return data.data
}

export async function listTemplates(): Promise<SkillTemplate[]> {
  const { data } = await request.get<SkillResponse<Array<SkillTemplate | string>>>('/skill/templates')
  return data.data.map((item) => {
    if (typeof item === 'string') {
      return { filename: item, name: item, description: '', tool_names: [], system_prompt: '' }
    }
    return item
  })
}

export async function listTools(): Promise<SkillTool[]> {
  const { data } = await request.get<SkillResponse<SkillTool[]>>('/skill/tools')
  return data.data
}

export async function getTemplate(filename: string): Promise<SkillTemplate> {
  const { data } = await request.get<SkillResponse<SkillTemplate>>(`/skill/templates/${encodeTemplatePath(filename)}`)
  return data.data
}

export async function createTemplate(payload: {
  name: string
  description: string
  system_prompt: string
  tool_names: string[]
}): Promise<SkillTemplate> {
  const { data } = await request.post<SkillResponse<SkillTemplate>>('/skill/templates', payload)
  return data.data
}

export async function updateTemplate(filename: string, payload: {
  name: string
  description: string
  system_prompt: string
  tool_names: string[]
}): Promise<SkillTemplate> {
  const { data } = await request.put<SkillResponse<SkillTemplate>>(`/skill/templates/${encodeTemplatePath(filename)}`, payload)
  return data.data
}

export async function deleteTemplate(filename: string): Promise<void> {
  await request.delete(`/skill/templates/${encodeTemplatePath(filename)}`)
}

// ===== 创建/更新/删除 =====
export async function createSkill(payload: {
  name: string
  description: string
  template_filename?: string
  is_public: number
  system_prompt?: string
  tool_names?: string[]
  permissions?: Partial<SkillPermissions>
}): Promise<Skill> {
  const { data } = await request.post<SkillResponse<Skill>>('/skill/', payload)
  return data.data
}

export async function updateSkill(skillId: number, payload: {
  name?: string
  description?: string
  template_filename?: string
  is_public?: number
  system_prompt?: string
  tool_names?: string[]
  permissions?: Partial<SkillPermissions>
}): Promise<Skill> {
  const { data } = await request.put<SkillResponse<Skill>>(`/skill/${skillId}`, payload)
  return data.data
}

export async function deleteSkill(skillId: number): Promise<void> {
  await request.delete(`/skill/${skillId}`)
}

export interface ImportedSkill extends Skill {
  /** 导入时的差异说明：哪些内容被忽略、为什么 */
  notes: string[]
  resource_count: number
  prompt_resource_count: number
  /** 保存下来的 Python 脚本数（沙箱开启后助手才能运行） */
  script_count: number
}

export interface SkillImportResult {
  imported: ImportedSkill[]
  failed: { name: string; error: string }[]
}

export async function importSkill(file: File, isPublic = 0): Promise<SkillImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('is_public', String(isPublic))
  const { data } = await request.post<SkillResponse<SkillImportResult>>('/skill/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data
}

/** 用当前用户自己的聊天模型，把 Skill 的名称和说明翻译成中文并保存 */
export async function translateSkill(skillId: number): Promise<Skill> {
  const { data } = await request.post<SkillResponse<Skill>>(`/skill/${skillId}/translate`)
  return data.data
}

export async function importSkillFromGithub(url: string, isPublic = 0): Promise<SkillImportResult> {
  const { data } = await request.post<SkillResponse<SkillImportResult>>('/skill/import/github', {
    url,
    is_public: isPublic,
  })
  return data.data
}

export async function exportSkill(skillId: number): Promise<Blob> {
  const { data } = await request.get(`/skill/${skillId}/export`, { responseType: 'blob' })
  return data as Blob
}

export async function installPublicSkill(skillId: number): Promise<Skill> {
  const { data } = await request.post<SkillResponse<Skill>>(`/skill/${skillId}/install`)
  return data.data
}
