import request from '../utils/request'

export interface Conversation {
  id: number
  user_id: number
  agent_id: number
  title: string
  is_pinned: number
  is_archived: number
  create_time: string
  update_time: string
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  create_time: string
}

/** GET /conversation/agent/{agent_id} 查 Agent 的会话列表 */
export async function listConversations(agentId: number): Promise<Conversation[]> {
  const { data } = await request.get(`/conversation/agent/${agentId}`)
  return data as Conversation[]
}

/** GET /conversation/{conversation_id}/messages 查会话内消息 */
export async function listMessages(conversationId: number): Promise<Message[]> {
  const { data } = await request.get(`/conversation/${conversationId}/messages`)
  return data as Message[]
}

/** PUT /conversation/{conversation_id} 改标题 */
export async function updateConversationTitle(conversationId: number, title: string): Promise<Conversation> {
  const { data } = await request.put(`/conversation/${conversationId}`, { title })
  return data as Conversation
}

export async function updateConversationFlags(
  conversationId: number,
  payload: { is_pinned?: number; is_archived?: number },
): Promise<Conversation> {
  const { data } = await request.patch(`/conversation/${conversationId}/flags`, payload)
  return data as Conversation
}

/** DELETE /conversation/{conversation_id} 删除会话 */
export async function deleteConversation(conversationId: number) {
  const { data } = await request.delete(`/conversation/${conversationId}`)
  return data
}

export async function exportConversation(conversationId: number, format: 'markdown' | 'json' = 'markdown'): Promise<Blob> {
  const { data } = await request.get(`/conversation/${conversationId}/export`, {
    params: { format },
    responseType: 'blob',
  })
  return data as Blob
}
