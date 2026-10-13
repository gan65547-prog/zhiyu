import request from './request'
import type { Conversation, ConversationCreate, ConversationUpdate, Message } from '@/types/chat'

export const conversationApi = {
  list: async (params?: { dataset_id?: string; page?: number; page_size?: number }) => {
    const response = await request.get<{ items: Conversation[]; total: number }>('/conversations', {
      params
    })
    return response
  },

  get: async (id: string) => {
    const response = await request.get<Conversation>(`/conversations/${id}`)
    return response
  },

  create: async (data: ConversationCreate) => {
    const response = await request.post<Conversation>('/conversations', data)
    return response
  },

  update: async (id: string, data: ConversationUpdate) => {
    const response = await request.put<Conversation>(`/conversations/${id}`, data)
    return response
  },

  delete: async (id: string) => {
    await request.delete(`/conversations/${id}`)
  },

  getMessages: async (id: string, params?: { page?: number; page_size?: number }) => {
    const response = await request.get<{ items: Message[]; total: number }>(
      `/conversations/${id}/messages`,
      { params }
    )
    return response
  },

  clearMessages: async (id: string) => {
    await request.delete(`/conversations/${id}/messages`)
  }
}
