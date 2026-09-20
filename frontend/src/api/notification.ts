import request from '../utils/request'

export interface NotificationChannel {
  id: number
  name: string
  kind: string
  webhook_url: string
  is_enabled: boolean
  last_sent_at: string | null
  last_error: string | null
}

export async function listNotificationChannels(): Promise<NotificationChannel[]> {
  const { data } = await request.get('/notification-channels')
  return data as NotificationChannel[]
}

export async function createNotificationChannel(name: string, webhookUrl: string): Promise<NotificationChannel> {
  const { data } = await request.post('/notification-channels', { name, webhook_url: webhookUrl })
  return data as NotificationChannel
}

export async function updateNotificationChannel(
  channelId: number,
  patch: { name?: string; webhook_url?: string; is_enabled?: boolean },
): Promise<NotificationChannel> {
  const { data } = await request.patch(`/notification-channels/${channelId}`, patch)
  return data as NotificationChannel
}

export async function deleteNotificationChannel(channelId: number) {
  const { data } = await request.delete(`/notification-channels/${channelId}`)
  return data
}

export async function testNotificationChannel(channelId: number): Promise<{ message: string }> {
  const { data } = await request.post(`/notification-channels/${channelId}/test`)
  return data
}
