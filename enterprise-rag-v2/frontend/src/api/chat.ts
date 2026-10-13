import request from './request'
import type { ChatRequest } from '@/types'

export interface ChatReadiness {
  ready: boolean
  indexed_documents: number
  processing_documents: number
  failed_documents: number
  provider: string
  provider_status: string
  reasons: string[]
  actions: string[]
}

export const chat = (data: ChatRequest) => {
  return request.post<any, any>('/api/v1/chat/', data).then(res => res.data || res)
}

export const getConversations = (params?: {
  dataset_id?: string
  page?: number
  page_size?: number
}) => {
  return request.get<any, any>('/api/v1/chat/conversations', { params })
}

export const getConversationMessages = (
  id: string,
  params?: { page?: number; page_size?: number }
) => {
  return request.get<any, any>(
    `/api/v1/chat/conversations/${id}/messages`,
    { params }
  )
}

export const deleteConversation = (id: string) => {
  return request.delete<any, any>(`/api/v1/chat/conversations/${id}`)
}

export const submitAsyncChatJob = (data: ChatRequest) => {
  return request.post<any, any>('/api/v1/chat/async', data)
}

export const getAsyncChatJobStatus = (jobId: string) => {
  return request.get<any, any>(`/api/v1/chat/jobs/${jobId}`)
}

export const getChatReadiness = (datasetId: string) => {
  return request.get<any, ChatReadiness>('/api/v1/chat/readiness', { params: { dataset_id: datasetId } })
}

// 导入认证状态管理
import { useAuthStore } from '@/stores/auth'

export const chatStream = async (
  data: ChatRequest,
  onMessage: (content: string) => void,
  onSources?: (sources: any[]) => void,
  onDone?: (info: any) => void,
  abortController?: AbortController,
  /** 每条 SSE 都可能带 conversation_id；需在首包就写入 store，否则切页时还未 done，恢复逻辑拿不到会话 id */
  onConversationId?: (conversationId: string) => void
) => {
  // 从认证状态管理中获取token
  try {
    let token = ''
    try {
      const authStore = useAuthStore()
      token = authStore.token
    } catch (e) {
      // ignore
    }

    const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (token && token !== 'cookie-session') {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${baseURL}/chat/stream`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify(data),
      signal: abortController?.signal
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    if (!reader) {
      throw new Error('Response body is null')
    }
    
    let buffer = ''
    let lastNotifiedConversationId = ''

    const notifyConversationId = (raw: Record<string, unknown>) => {
      const cid = raw?.conversation_id
      if (cid == null || !onConversationId) return
      const s = String(cid)
      if (s && s !== lastNotifiedConversationId) {
        lastNotifiedConversationId = s
        onConversationId(s)
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      
      // 保留最后一行（可能不完整）
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const dataStr = line.slice(6).trim()
            if (!dataStr) continue
            
            const data = JSON.parse(dataStr) as Record<string, unknown>
            notifyConversationId(data)

            // 支持两种格式：直接delta格式 或 event格式
            if (data.delta !== undefined) {
              // 后端直接返回delta格式
              onMessage(data.delta as string)
            } else if (data.event === 'message' && data.data) {
              // event格式
              onMessage(data.data as string)
            } else if (data.event === 'sources' && data.data) {
              onSources?.(data.data as any[])
            } else if (data.event === 'done') {
              onDone?.(data.data)
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e, 'Line:', line)
          }
        }
      }
    }
  } catch (e) {
    console.error('Error in chatStream:', e)
    throw e
  }
}
