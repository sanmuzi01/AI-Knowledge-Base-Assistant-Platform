import request from '../utils/request'

export interface Attachment {
  id: string
  name: string
  size: number
}

export interface AttachmentStatus {
  /** 脚本沙箱是否开启；没开时不显示上传入口 */
  enabled: boolean
  max_bytes: number
}

export async function getAttachmentStatus(): Promise<AttachmentStatus> {
  const { data } = await request.get<AttachmentStatus>('/attachment/status')
  return data
}

export async function uploadAttachment(file: File): Promise<Attachment> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await request.post<Attachment>('/attachment', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
