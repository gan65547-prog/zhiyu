import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getConversations as getConversationsApi,
  getConversationMessages as getMessagesApi,
  deleteConversation as deleteConversationApi
} from '@/api/chat'
import type { Conversation, Message } from '@/types'
import { useAuthStore } from './auth'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<Message[]>([])
  /** 会话列表请求中的加载（可与 silent 刷新分离，避免拖住整页与其它路由观感） */
  const conversationsListLoading = ref(false)
  /** 拉取某会话消息历史时的加载 */
  const messagesLoading = ref(false)
  const total = ref(0)
  const streaming = ref(false)
  const currentAssistantMessage = ref<any>(null)
  const abortController = ref<AbortController | null>(null)

  // 从认证状态管理中获取登录状态
  const isLoggedIn = computed(() => {
    try {
      const authStore = useAuthStore()
      return authStore.isLoggedIn
    } catch (e) {
      return false
    }
  })

  // 检查用户是否是超级管理员
  const isSuperuser = computed(() => {
    try {
      const authStore = useAuthStore()
      return authStore.isSuperuser
    } catch (e) {
      return false
    }
  })

  async function fetchConversations(
    datasetId?: string,
    options?: { silent?: boolean }
  ) {
    const silent = options?.silent === true
    // 超级管理员不获取会话
    if (isSuperuser.value) {
      conversations.value = []
      total.value = 0
      return
    }
    
    // 如果用户未登录，直接返回空数组
    if (!isLoggedIn.value) {
      conversations.value = []
      total.value = 0
      return
    }
    
    if (!silent) {
      conversationsListLoading.value = true
    }
    try {
      const res = await getConversationsApi({ dataset_id: datasetId })
      console.log('fetchConversations response:', res)
      // 检查 res 是否已经是 data 对象（因为 request 拦截器返回的是 response.data）
      if (res.data !== undefined) {
        // 如果 res 有 data 属性，说明它是完整的响应对象
        conversations.value = res.data || []
        total.value = res.total || 0
      } else {
        // 如果 res 没有 data 属性，说明它已经是 data 对象
        if (Array.isArray(res)) {
          // 如果 res 是数组，直接使用
          conversations.value = res
          total.value = res.length
        } else if (res && typeof res === 'object' && res.data !== undefined) {
          // 如果 res 是对象且有 data 属性，使用 res.data
          conversations.value = res.data || []
          total.value = res.total || 0
        } else {
          // 其他情况，使用空数组
          conversations.value = []
          total.value = 0
        }
      }
      console.log('fetchConversations conversations:', conversations.value)
      return res
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status !== 429) console.error('fetchConversations error:', error)
      conversations.value = []
      total.value = 0
      return null
    } finally {
      if (!silent) {
        conversationsListLoading.value = false
      }
    }
  }

  async function fetchMessages(conversationId: string) {
    // 超级管理员不获取消息
    if (isSuperuser.value) {
      messages.value = []
      total.value = 0
      return
    }
    
    // 确保认证状态已初始化
    try {
      const authStore = useAuthStore()
      if (!authStore.initialized) {
        await authStore.initialize()
      }
    } catch (e) {
      console.error('Error initializing auth store:', e)
    }
    
    // 如果用户未登录，直接返回空数组
    if (!isLoggedIn.value) {
      messages.value = []
      total.value = 0
      return
    }
    
    messagesLoading.value = true
    try {
      console.log('fetchMessages: calling getMessagesApi with conversationId:', conversationId)
      const res = await getMessagesApi(conversationId)
      console.log('fetchMessages response:', res)
      // 处理后端返回的消息格式（兼容仅含 data 数组、省略 success 等情况）
      let messagesData: any[] = []
      let totalCount = 0

      if (Array.isArray(res)) {
        messagesData = res
        totalCount = res.length
      } else if (res && typeof res === 'object') {
        const raw = res as Record<string, unknown>
        if (Array.isArray(raw.data)) {
          messagesData = raw.data as any[]
          totalCount = messagesData.length
        } else if (Array.isArray(raw.items)) {
          messagesData = raw.items as any[]
          totalCount = messagesData.length
        }
      }
      
      console.log('fetchMessages: messagesData:', messagesData)
      console.log('fetchMessages: totalCount:', totalCount)

      const hadLocal = messages.value.length > 0
      if (
        hadLocal &&
        messagesData.length === 0 &&
        currentConversation.value?.id === conversationId
      ) {
        console.warn(
          'fetchMessages: 服务端返回空数组，保留本地已展示消息（常见于回答过程中切页、落库尚未完成）'
        )
        total.value = 0
        return res
      }

      // 处理消息格式，将 retrieved_chunks 转换为 sources
      messages.value = messagesData.map((msg: any) => {
        // 将 retrieved_chunks 转换为 sources 格式
        if (msg.retrieved_chunks && Array.isArray(msg.retrieved_chunks)) {
          return {
            ...msg,
            sources: msg.retrieved_chunks
              .filter((chunk: any) => !!chunk)
              .map((chunk: any) => ({
              document_id: chunk.document_id || chunk.metadata?.document_id,
              document_name: chunk.document_name || chunk.metadata?.file_name || chunk.metadata?.document_name,
              content: chunk.content || chunk.text,
              score: chunk.score || 0,
              chapter:
                chunk.chapter ||
                chunk.metadata?.chapter ||
                chunk.metadata?.chapter_title ||
                chunk.metadata?.section ||
                chunk.metadata?.heading,
              metadata: chunk.metadata || {}
            }))
          }
        }
        // 确保消息格式包含 sources 字段
        return {
          ...msg,
          sources: msg.sources || []
        }
      })
      total.value = totalCount
      console.log('fetchMessages: messages.value:', messages.value)
      return res
    } catch (error: any) {
      console.error('fetchMessages error:', error)
      console.error('fetchMessages error status:', error.response?.status)
      console.error('fetchMessages error data:', error.response?.data)
      // 处理 404 错误
      if (error.response?.status === 404) {
        // 清除当前会话
        setCurrentConversation(null)
        // 从会话列表中删除不存在的会话
        conversations.value = conversations.value.filter(c => c.id !== conversationId)
        // 显示友好的错误提示
        import('element-plus').then(({ ElMessage }) => {
          ElMessage.error('会话不存在或已被删除')
        })
      }
      // 处理 401 错误
      else if (error.response?.status === 401) {
        // 清除 token 并跳转到登录页面
        const authStore = useAuthStore()
        authStore.logout()
        // 跳转到登录页面
        import('vue-router').then(({ useRouter }) => {
          const router = useRouter()
          router.push('/login')
        })
      }
      messages.value = []
      total.value = 0
      return null
    } finally {
      messagesLoading.value = false
    }
  }

  async function deleteConversation(id: string) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      return
    }
    
    try {
      await deleteConversationApi(id)
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentConversation.value?.id === id) {
        currentConversation.value = null
        messages.value = []
        streaming.value = false
        currentAssistantMessage.value = null
      }
    } catch (error) {
      console.error('deleteConversation error:', error)
    }
  }

  function setCurrentConversation(conversation: Conversation | null) {
    currentConversation.value = conversation
  }

  /** 流式 SSE 首包即可带上 conversation_id，在 done 前写入，便于切页后仍能关联会话并拉历史 */
  function applyStreamConversationShell(conversationId: string, datasetId: string) {
    if (!conversationId || !datasetId) return
    const existing = currentConversation.value
    if (existing?.id === conversationId) return
    if (existing && existing.id !== conversationId) return
    const now = new Date().toISOString()
    currentConversation.value = {
      id: conversationId,
      dataset_id: datasetId,
      title: existing?.title || '新会话',
      metadata: existing?.metadata ?? {},
      created_at: existing?.created_at || now,
      updated_at: now
    }
  }

  function addMessage(message: Message) {
    messages.value.push(message)
  }

  function clearMessages() {
    messages.value = []
    currentAssistantMessage.value = null
  }

  function setStreaming(status: boolean) {
    streaming.value = status
  }

  function setCurrentAssistantMessage(message: any) {
    currentAssistantMessage.value = message
  }

  function setAbortController(controller: AbortController | null) {
    abortController.value = controller
  }

  function resetTransientState() {
    conversationsListLoading.value = false
    messagesLoading.value = false
    streaming.value = false
    currentAssistantMessage.value = null
    abortController.value = null
  }

  /** 登录/登出/切换租户或工作空间时清空会话与消息，避免跨身份展示残留聊天记录 */
  function resetAllState() {
    conversations.value = []
    currentConversation.value = null
    messages.value = []
    total.value = 0
    resetTransientState()
  }

  /** 兼容旧代码：任一会话列表或消息拉取中为 true（新界面应优先用分项 loading） */
  const loading = computed(
    () => conversationsListLoading.value || messagesLoading.value
  )

  return {
    conversations,
    currentConversation,
    messages,
    loading,
    conversationsListLoading,
    messagesLoading,
    total,
    streaming,
    currentAssistantMessage,
    abortController,
    fetchConversations,
    fetchMessages,
    deleteConversation,
    setCurrentConversation,
    applyStreamConversationShell,
    addMessage,
    clearMessages,
    setStreaming,
    setCurrentAssistantMessage,
    setAbortController,
    resetTransientState,
    resetAllState
  }
})
