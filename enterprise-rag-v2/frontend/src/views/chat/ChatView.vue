<template>
  <div class="chat-view">
    <div class="sidebar">
      <div class="sidebar-header">
        <h3>会话历史</h3>
        <el-button
          type="primary"
          size="small"
          @click="handleNewChat"
        >
          <el-icon><Plus /></el-icon>
          新会话
        </el-button>
      </div>

      <div
        v-if="chatStore.conversationsListLoading"
        class="loading"
      >
        <LoadingSpinner />
      </div>

      <div
        v-else-if="displayedConversations.length === 0"
        class="empty"
      >
        <p>暂无会话记录</p>
      </div>

      <div
        v-else
        class="conversation-list"
      >
        <div
          v-for="conv in displayedConversations"
          :key="conv.id"
          class="conversation-item"
          :class="{ active: chatStore.currentConversation?.id === conv.id }"
          @click="selectConversation(conv)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <div class="conv-info">
            <span class="title">{{ conv.title }}</span>
            <span class="dataset-tag">{{ getDatasetName(conv.dataset_id) || '默认知识库' }}</span>
            <span class="time">{{ formatTime(conv.updated_at) }}</span>
          </div>
          <el-dropdown @command="(cmd: string) => handleConvCommand(cmd, conv)">
            <el-icon class="more-icon">
              <More />
            </el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="delete">
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <div class="chat-container">
      <div class="chat-header">
        <div class="chat-heading">
          <span class="section-kicker">KNOWLEDGE COPILOT</span>
          <h1>智能问答</h1>
          <span class="chat-heading-note">基于当前知识库继续追问，并保留可核验来源</span>
        </div>
        <el-select
          v-model="selectedDatasetId"
          placeholder="选择知识库"
          style="width: 240px"
          @change="handleDatasetChange"
        >
          <el-option
            v-for="ds in datasetStore.datasets"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          />
        </el-select>
        <el-tag
          v-if="selectedDatasetId"
          type="success"
          effect="plain"
          class="dataset-connection-tag"
        >
          <el-icon><CircleCheck /></el-icon>
          已连接知识库
        </el-tag>
        <el-alert
          v-if="selectedDatasetId && chatReadiness && !chatReadiness.ready"
          :title="chatReadiness.reasons.join('；') || '知识库还未准备好'"
          type="warning"
          :closable="false"
          show-icon
          class="chat-readiness-alert"
        />
        <el-button
          v-else-if="datasetStore.datasets.length === 0"
          link
          type="primary"
          @click="router.push('/datasets/create')"
        >
          先创建知识库
        </el-button>
      </div>

      <div
        ref="messageListRef"
        class="message-list"
      >
        <div
          v-if="chatStore.messagesLoading && chatStore.currentConversation"
          class="empty-state"
        >
          <LoadingSpinner text="加载历史消息..." />
        </div>
        <div
          v-else-if="isEmpty"
          class="empty-state"
        >
          <el-icon
            :size="64"
            color="#dcdfe6"
          >
            <ChatLineRound />
          </el-icon>
          <p v-if="chatStore.currentConversation">
            暂无消息，或加载失败（请查看网络请求）
          </p>
          <p v-else>
            {{ selectedDatasetId ? '从一个问题开始，把知识库变成可执行答案' : '先连接知识库，再开始对话' }}
          </p>
          <div v-if="!chatStore.currentConversation && selectedDatasetId" class="quick-prompts">
            <button
              v-for="prompt in quickPrompts"
              :key="prompt"
              type="button"
              class="quick-prompt"
              @click="useQuickPrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
        </div>

        <template v-else>
          <div
            v-for="(msg, index) in messages"
            :key="(msg as any).id || `msg-${index}`"
            :class="['message-item', msg.role]"
          >
            <div class="message-content">
              <div class="message-text">
                {{ maskToken(msg.content) }}
              </div>
              
              <!-- 显示检索到的文档（仅助手消息） -->
              <div
                v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0"
                class="retrieved-docs"
              >
                <el-collapse>
                  <el-collapse-item
                    title="参考文档"
                    name="1"
                  >
                    <div
                      v-for="(doc, docIndex) in msg.sources"
                      :key="docIndex"
                      class="doc-item"
                    >
                      <div class="doc-meta">
                        <span class="doc-book">书名：{{ getSourceBook(doc) }}</span>
                        <span class="doc-chapter">章节：{{ getSourceChapter(doc) }}</span>
                      </div>
                      <div class="doc-score">
                        相关度: {{ formatSourceScore(doc) }}
                      </div>
                      <div class="doc-content">
                        {{ getSourceContent(doc) }}
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
        </template>

        <div
          v-if="streaming"
          class="streaming-indicator"
        >
          <LoadingSpinner text="AI 正在思考..." />
        </div>
      </div>

      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入问题..."
          :disabled="!selectedDatasetId || Boolean(chatReadiness && !chatReadiness.ready)"
          @keydown.enter.prevent="handleSend"
        />
        <el-button
          type="primary"
          :loading="sendButtonLoading"
          :disabled="!inputMessage.trim() || !selectedDatasetId || chatStore.messagesLoading || Boolean(chatReadiness && !chatReadiness.ready)"
          @click="handleSend"
        >
          <el-icon><Promotion /></el-icon>
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated, onBeforeUnmount, onDeactivated, watch, nextTick } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import { useChatStore } from '@/stores/chat'
import { useWorkspaceStore } from '@/stores/workspace'
import { useAuthStore } from '@/stores/auth'
import { Plus, ChatDotRound, ChatLineRound, Promotion, More, CircleCheck } from '@element-plus/icons-vue'
import { formatTime } from '@/utils/format'
import { ElMessageBox, ElMessage } from 'element-plus'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { submitAsyncChatJob, getAsyncChatJobStatus, getChatReadiness, type ChatReadiness } from '@/api/chat'
import type { Conversation } from '@/types'

const route = useRoute()
const router = useRouter()
const datasetStore = useDatasetStore()
const chatStore = useChatStore()
const workspaceStore = useWorkspaceStore()
const authStore = useAuthStore()

const selectedDatasetId = ref('')
const inputMessage = ref('')
const messageListRef = ref<HTMLElement>()
const quickPrompts = [
  '总结这套知识库的核心观点',
  '找出最值得继续研究的三个问题',
  '把相关内容整理成一份行动清单',
]

const useQuickPrompt = (prompt: string) => {
  inputMessage.value = prompt
}

/** 上次在问答页选中的知识库（组件销毁后 ref 会丢，会话记忆在 pinia；此项用于无会话仅选库时的恢复） */
const lastSelectedDatasetId = ref('')
/** 路由未使用 keep-alive 时，离开再进入只会走 onMounted，不会走 onActivated，须与恢复逻辑共用 */
const LAST_DATASET_STORAGE_KEY = 'enterprise-rag-chat:lastDatasetId'
const LAST_CONV_STORAGE_KEY = 'enterprise-rag-chat:lastConversationId'
/** 离开过问答页后再进入时置位，用于静默拉会话列表、减少「再次进入」时的转圈 */
const REVISIT_CHAT_FLAG_KEY = 'enterprise-rag-chat:revisitNext'

/** 当前是否在智能问答路由下，避免离开后后台流式/收尾逻辑影响其它页面 */
const chatViewActive = ref(true)

/** 客户端二次过滤会话列表：即使 store 被其他页面覆盖，只展示当前知识库的会话 */
const displayedConversations = computed(() => {
  if (!selectedDatasetId.value) return chatStore.conversations
  return chatStore.conversations.filter(c => {
    const cid = String(c.dataset_id ?? '')
    const sid = selectedDatasetId.value
    if (cid === sid) return true
    return resolveCanonicalDatasetId(cid) === sid
  })
})

function getDatasetName(datasetId: string): string {
  if (!datasetId) return ''
  const found = datasetStore.datasets.find(d => d.id === datasetId)
  return found?.name ?? ''
}

watch(selectedDatasetId, (v) => {
  if (v) {
    try {
      sessionStorage.setItem(LAST_DATASET_STORAGE_KEY, v)
    } catch {
      /* ignore */
    }
  }
})

/** 与 el-option 的 :value 对齐：会话 dataset_id 与知识库 id 可能仅有大小写/连字符差异，不匹配时 el-select 会异常并触发多余 change */
function normDatasetKey(s: string): string {
  return String(s ?? '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '')
}

function resolveCanonicalDatasetId(raw: string): string {
  const r = String(raw ?? '').trim()
  if (!r) return ''
  const list = datasetStore.datasets
  // 列表已加载时，未知 ID 必须视为无效；不能把旧账号/旧租户的
  // sessionStorage 或会话数据继续带入当前问答上下文。
  if (list.length === 0) return ''
  if (list.some((d) => d.id === r)) return r
  const nr = normDatasetKey(r)
  const hit = list.find((d) => normDatasetKey(String(d.id)) === nr)
  return hit ? String(hit.id) : ''
}

const messages = computed(() => chatStore.messages)
const streaming = computed(() => chatStore.streaming)

const isEmpty = computed(() => messages.value.length === 0)

/** 发送按钮 loading：流式生成中 */
const sendButtonLoading = computed(() => chatStore.streaming)
const chatReadiness = ref<ChatReadiness | null>(null)
const chatJobPollingToken = ref(0)


const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const waitAsyncChatJobDone = async (jobId: string, pollingToken: number) => {
  const maxAttempts = 240 // 最长约6分钟
  for (let i = 0; i < maxAttempts; i += 1) {
    if (!chatViewActive.value || chatJobPollingToken.value !== pollingToken) {
      return null
    }
    const statusResp = await getAsyncChatJobStatus(jobId)
    const data = statusResp?.data || statusResp
    const status = String(data?.status || '').toUpperCase()
    if (status === 'SUCCESS') {
      return data?.result || {}
    }
    if (status === 'FAILURE') {
      throw new Error(data?.error || '异步任务执行失败')
    }
    await sleep(1500)
  }
  throw new Error('等待响应超时，请稍后刷新会话')
}

// 脱敏处理：隐藏token
const maskToken = (content: string) => {
  if (!content) return ''
  let maskedContent = content
  // 匹配token: "value" 或 token="value" 格式
  maskedContent = maskedContent.replace(/(token|access_token|auth_token|api_key)\s*[:=]\s*['"]([a-zA-Z0-9_\-]+)['"]/gi, '$1: [REDACTED]')
  // 匹配 Bearer token 格式
  maskedContent = maskedContent.replace(/(Bearer|Token)\s+([a-zA-Z0-9_\-\.]+)/gi, '$1 [REDACTED]')
  return maskedContent
}

const getSourceBook = (source: any) => {
  if (!source || typeof source !== 'object') return '未知书籍'
  return (
    source?.document_name ||
    source?.metadata?.file_name ||
    source?.metadata?.document_name ||
    '未知书籍'
  )
}

const getSourceChapter = (source: any) => {
  if (!source || typeof source !== 'object') return '未标注章节'
  const metadataChapter =
    source?.chapter ||
    source?.metadata?.chapter ||
    source?.metadata?.chapter_title ||
    source?.metadata?.section ||
    source?.metadata?.heading
  if (metadataChapter) return metadataChapter

  const content = String(source?.content || '')
  const chapterMatch = content.match(/(第[一二三四五六七八九十百千万0-9]+[章节卷篇]|Chapter\s*\d+|CHAPTER\s*\d+)/)
  if (chapterMatch?.[1]) return chapterMatch[1]

  return (
    '未标注章节'
  )
}

const getSourceContent = (source: any) => {
  if (!source || typeof source !== 'object') return ''
  return String(source.content || '')
}

const formatSourceScore = (source: any) => {
  if (!source || typeof source !== 'object') return '0.0%'
  const score = Number(source.score || 0)
  if (Number.isNaN(score)) return '0.0%'
  return `${(score * 100).toFixed(1)}%`
}

const stopWorkspaceWatch = watch(() => workspaceStore.currentWorkspaceId, async () => {
  await datasetStore.fetchDatasets({ silent: true })
  selectedDatasetId.value = ''
  chatStore.resetAllState()
  if (!authStore.isSuperuser) {
    await chatStore.fetchConversations(undefined, { silent: true })
  }
})

/**
 * 从左侧会话列表点选会话时会同步 v-model 到该会话的 dataset_id。
 * el-select 可能在此后触发 @change；若 change 晚于 fetchMessages 完成，
 * handleDatasetChange 里的 clearMessages 会清空刚拉取的消息，表现为「点了历史记录却空白」。
 * 在「由历史记录驱动」的切换窗口内跳过 clearMessages，只刷新会话列表。
 */
const suppressDatasetClearFromHistory = ref(false)

const handleDatasetChange = async () => {
  if (!suppressDatasetClearFromHistory.value) {
    chatStore.clearMessages()
    // 切换知识库时重置当前会话，避免旧知识库的会话泄露到新知识库
    chatStore.setCurrentConversation(null)
    try {
      sessionStorage.removeItem(LAST_CONV_STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }
  // 切换知识库后，获取该知识库对应的会话列表
  if (selectedDatasetId.value) {
    chatReadiness.value = await getChatReadiness(selectedDatasetId.value).catch(() => null)
    await chatStore.fetchConversations(selectedDatasetId.value)
  } else {
    chatReadiness.value = null
    // 如果未选择知识库，获取所有会话
    await chatStore.fetchConversations()
  }
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || !selectedDatasetId.value) return

  const userMessage: import('@/types/chat').Message = {
    id: crypto.randomUUID(),
    role: 'user',
    content: inputMessage.value,
    created_at: new Date().toISOString()
  }
  
  chatStore.addMessage(userMessage)
  const query = inputMessage.value
  inputMessage.value = ''
  
  // 创建助手消息占位符
  const assistantMessage: import('@/types/chat').Message = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '正在处理中，请稍候...',
    sources: [],
    created_at: new Date().toISOString()
  }
  chatStore.addMessage(assistantMessage)
  chatStore.setCurrentAssistantMessage(assistantMessage)
  chatStore.setStreaming(true)
  
  try {
    const submitResp = await submitAsyncChatJob({
      dataset_id: selectedDatasetId.value,
      query: query,
      conversation_id: chatStore.currentConversation?.id,
      history: chatStore.messages.slice(0, -1).map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at
      }))
    })
    const submitData = submitResp?.data || submitResp
    const jobId = String(submitData?.job_id || '')
    if (!jobId) {
      throw new Error('未获取到任务ID')
    }

    const pollingToken = chatJobPollingToken.value + 1
    chatJobPollingToken.value = pollingToken
    const result = await waitAsyncChatJobDone(jobId, pollingToken)
    if (!result) return

    const conversationId = result?.conversation_id ? String(result.conversation_id) : ''
    if (conversationId) {
      chatStore.applyStreamConversationShell(conversationId, selectedDatasetId.value)
      try {
        sessionStorage.setItem(LAST_CONV_STORAGE_KEY, conversationId)
      } catch {
        /* ignore */
      }
    }
    await chatStore.fetchConversations(selectedDatasetId.value, { silent: true })
    if (conversationId) {
      await chatStore.fetchMessages(conversationId)
    } else if (chatStore.currentConversation?.id) {
      await chatStore.fetchMessages(chatStore.currentConversation.id)
    }
  } catch (error: any) {
    // 忽略中止错误
    if (error.name !== 'AbortError') {
      console.error('发送消息失败:', error)
      ElMessage.error('发送消息失败: ' + (error.message || '未知错误'))
      
      // 移除失败的助手消息
      if (chatStore.messages.length > 0 && chatStore.messages[chatStore.messages.length - 1].role === 'assistant') {
        chatStore.messages.pop()
      }
      
      // 显示错误提示
      chatStore.addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content:
          '请求未成功（多为网络或后端异常）。请查看后端日志；并确认：向量服务可访问、已配置有效的大模型 API 或 Ollama、知识库文档已入库索引。',
        sources: [],
        created_at: new Date().toISOString()
      })
    }
  } finally {
    chatStore.setStreaming(false)
    scrollToBottom()
    // 发送消息后静默刷新会话列表（已离开智能问答页则不再请求）
    if (chatViewActive.value) {
      chatStore.fetchConversations(selectedDatasetId.value, { silent: true })
    }
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

/** 长消息在 DOM 更新后高度才正确，切回页面时多拍一帧再滚到底，避免只看到上半截 */
const scrollToBottomAfterLayout = () => {
  nextTick(() => {
    nextTick(() => {
      requestAnimationFrame(() => {
        scrollToBottom()
        requestAnimationFrame(() => scrollToBottom())
      })
    })
  })
}

/**
 * 从其它路由回到 /chat 时：默认无 keep-alive，组件会重新挂载，只触发 onMounted，不会触发 onActivated。
 * 因此必须把「恢复知识库下拉 + 拉会话列表 + 拉当前会话消息」放在此处，否则消息区会一直空。
 * 注意：切勿在仅因路由带 datasetId 时调用 handleDatasetChange()，否则会 clearMessages。
 */
async function restoreChatViewAfterNavigation(options?: { conversationsSilent?: boolean }) {
  const conversationsSilent = options?.conversationsSilent !== false

  await datasetStore.fetchDatasets({ silent: true })

  const datasetIdFromRoute = ((route.params.datasetId as string) || '').trim()
  let savedFromStorage = ''
  try {
    savedFromStorage = sessionStorage.getItem(LAST_DATASET_STORAGE_KEY) || ''
  } catch {
    savedFromStorage = ''
  }

  if (chatStore.currentConversation?.dataset_id) {
    const ds = resolveCanonicalDatasetId(String(chatStore.currentConversation.dataset_id))
    const cur = resolveCanonicalDatasetId(String(selectedDatasetId.value ?? ''))
    if (ds && ds !== cur) {
      suppressDatasetClearFromHistory.value = true
      selectedDatasetId.value = ds
      await nextTick()
    }
  } else if (datasetIdFromRoute) {
    const canon = resolveCanonicalDatasetId(datasetIdFromRoute)
    const cur = resolveCanonicalDatasetId(String(selectedDatasetId.value ?? ''))
    if (canon && canon !== cur) {
      suppressDatasetClearFromHistory.value = true
      selectedDatasetId.value = canon
      await nextTick()
    }
  } else if (lastSelectedDatasetId.value) {
    const last = resolveCanonicalDatasetId(String(lastSelectedDatasetId.value))
    const cur = resolveCanonicalDatasetId(String(selectedDatasetId.value ?? ''))
    if (last && last !== cur) {
      suppressDatasetClearFromHistory.value = true
      selectedDatasetId.value = last
      await nextTick()
    }
  } else if (savedFromStorage) {
    const saved = resolveCanonicalDatasetId(savedFromStorage)
    const cur = resolveCanonicalDatasetId(String(selectedDatasetId.value ?? ''))
    if (saved && saved !== cur) {
      suppressDatasetClearFromHistory.value = true
      selectedDatasetId.value = saved
      await nextTick()
    }
  }

  // 只有一个知识库时直接建立上下文，避免用户进入问答页后看到“选择知识库”
  // 却无法输入问题；多个知识库仍要求用户明确选择，避免误用上下文。
  if (!selectedDatasetId.value && datasetStore.datasets.length === 1) {
    selectedDatasetId.value = String(datasetStore.datasets[0].id)
    lastSelectedDatasetId.value = selectedDatasetId.value
    await nextTick()
  }

  if (selectedDatasetId.value) {
    chatReadiness.value = await getChatReadiness(selectedDatasetId.value).catch(() => null)
    await chatStore.fetchConversations(selectedDatasetId.value, { silent: conversationsSilent })
  } else {
    await chatStore.fetchConversations(undefined, { silent: conversationsSilent })
  }

  if (!chatStore.currentConversation?.id) {
    try {
      const cid = sessionStorage.getItem(LAST_CONV_STORAGE_KEY)
      if (cid) {
        const hit = chatStore.conversations.find((c) => c.id === cid)
        if (hit) chatStore.setCurrentConversation(hit)
      }
    } catch {
      /* ignore */
    }
  }

  // 在当前知识库中选一个最近的会话，避免页面空白
  if (!chatStore.currentConversation?.id && chatStore.conversations.length > 0) {
    const latest = [...chatStore.conversations].sort((a, b) => {
      const ta = new Date(a.updated_at || a.created_at || 0).getTime()
      const tb = new Date(b.updated_at || b.created_at || 0).getTime()
      return tb - ta
    })[0]
    if (latest) {
      chatStore.setCurrentConversation(latest)
      const canonical = resolveCanonicalDatasetId(String(latest.dataset_id ?? ''))
      if (canonical) {
        selectedDatasetId.value = canonical
      }
      try {
        sessionStorage.setItem(LAST_CONV_STORAGE_KEY, latest.id)
      } catch {
        /* ignore */
      }
    }
  }

  if (chatStore.currentConversation?.id) {
    await chatStore.fetchMessages(chatStore.currentConversation.id)
    scrollToBottomAfterLayout()
  } else {
    scrollToBottom()
  }

  setTimeout(() => {
    suppressDatasetClearFromHistory.value = false
  }, 320)
}

watch(() => chatStore.messages, scrollToBottom, { deep: true })

const selectConversation = async (conv: Conversation) => {
  try {
    if (datasetStore.datasets.length === 0) {
      await datasetStore.fetchDatasets({ silent: true })
    }
    chatStore.setCurrentConversation(conv)
    const targetDs = resolveCanonicalDatasetId(String(conv.dataset_id ?? ''))
    const currentDs = resolveCanonicalDatasetId(String(selectedDatasetId.value ?? ''))
    // 同一知识库内切换会话时不要改 v-model，避免触发 el-select @change → clearMessages
    if (targetDs && targetDs !== currentDs) {
      suppressDatasetClearFromHistory.value = true
      selectedDatasetId.value = targetDs
      await nextTick()
    }
    await chatStore.fetchMessages(conv.id)
    lastSelectedDatasetId.value = conv.dataset_id
    try {
      sessionStorage.setItem(LAST_CONV_STORAGE_KEY, conv.id)
    } catch {
      /* ignore */
    }
    await nextTick()
    setTimeout(() => {
      suppressDatasetClearFromHistory.value = false
    }, 320)
  } catch (error) {
    console.error('Error selecting conversation:', error)
    suppressDatasetClearFromHistory.value = false
    chatStore.setCurrentConversation(null)
    chatStore.clearMessages()
  }
}

const handleNewChat = () => {
  chatStore.setCurrentConversation(null)
  chatStore.clearMessages()
  // 新会话仍然属于当前已选知识库；清空它会让输入框立即禁用，
  // 用户不得不重新选择一次知识库才能继续问答。
  if (selectedDatasetId.value) {
    lastSelectedDatasetId.value = selectedDatasetId.value
  }
  try {
    sessionStorage.removeItem(LAST_CONV_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

const handleConvCommand = async (command: string, conv: Conversation) => {
  if (command === 'delete') {
    await ElMessageBox.confirm('确定删除该会话吗？', '提示', { type: 'warning' })
    await chatStore.deleteConversation(conv.id)
    ElMessage.success('删除成功')
    if (chatStore.currentConversation?.id === conv.id) {
      handleNewChat()
    }
  }
}

onMounted(async () => {
  console.log('ChatView onMounted: restore (含从其它路由再次进入 /chat，无 keep-alive 仅走此处)')
  await authStore.initialize()
  if (!authStore.isSuperuser) {
    let revisit = false
    try {
      revisit = sessionStorage.getItem(REVISIT_CHAT_FLAG_KEY) === '1'
      if (revisit) sessionStorage.removeItem(REVISIT_CHAT_FLAG_KEY)
    } catch {
      revisit = false
    }
    // 首次进入问答页：会话列表可显示 loading；从其它页返回：静默刷新，避免与「其它页不要转圈」的体验冲突
    await restoreChatViewAfterNavigation({ conversationsSilent: revisit })
  }
})

// 若将来外层包了 keep-alive，从缓存激活时走这里（与 onMounted 共用恢复逻辑）
onActivated(async () => {
  console.log('ChatView onActivated: restore (keep-alive)')
  chatViewActive.value = true
  if (!authStore.isSuperuser) {
    lastSelectedDatasetId.value = selectedDatasetId.value
    await restoreChatViewAfterNavigation({ conversationsSilent: true })
  }
})

// 离开智能问答页：仅标记失活，不主动中止流式请求。
// 这样切到其它页面时，后端 RAG 任务仍可继续并在 finally 落库；回到问答页再拉历史即可看到结果。
const teardownChatPage = () => {
  chatViewActive.value = false
  chatJobPollingToken.value += 1
  chatStore.resetTransientState()
}

onBeforeRouteLeave(() => {
  // 离开问答页前持久化当前选择，避免切页返回后恢复不到原会话
  try {
    if (selectedDatasetId.value) {
      sessionStorage.setItem(LAST_DATASET_STORAGE_KEY, selectedDatasetId.value)
    }
    if (chatStore.currentConversation?.id) {
      sessionStorage.setItem(LAST_CONV_STORAGE_KEY, chatStore.currentConversation.id)
    }
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.setItem(REVISIT_CHAT_FLAG_KEY, '1')
  } catch {
    /* ignore */
  }
  teardownChatPage()
})

onDeactivated(() => {
  teardownChatPage()
})

onBeforeUnmount(() => {
  stopWorkspaceWatch()
  teardownChatPage()
})
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  height: calc(100vh - 60px - 40px);
  margin: -22px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);

  .sidebar {
    width: 280px;
    background: rgba(248, 250, 252, 0.92);
    border-right: 1px solid rgba(148, 163, 184, 0.2);
    display: flex;
    flex-direction: column;

    .sidebar-header {
      padding: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(148, 163, 184, 0.2);

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
      }
    }

    .loading,
    .empty {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #827a90;
    }

    .conversation-list {
      flex: 1;
      overflow-y: auto;

      .conversation-item {
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        transition: background 0.2s;
        border-bottom: 1px solid rgba(226, 232, 240, 0.7);
        border-left: 2px solid transparent;

        &:hover {
          background: rgba(112, 74, 198, 0.08);

          .more-icon {
            opacity: 1;
          }
        }

        &.active {
          background: rgba(112, 74, 198, 0.12);
          border-left-color: #704ac6;
        }

        .conv-info {
          flex: 1;
          min-width: 0;

          .title {
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 14px;
          }

          .time {
            font-size: 12px;
            color: #999;
          }
        }

        .more-icon {
          opacity: 0;
          transition: opacity 0.2s;
        }
      }
    }
  }

  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: rgba(241, 245, 249, 0.64);

    .chat-header {
      padding: 16px;
      background: rgba(255, 255, 255, 0.82);
      border-bottom: 1px solid rgba(148, 163, 184, 0.2);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;

      .chat-heading {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 220px;
        margin-right: auto;

        .section-kicker {
          color: #8b6bd8;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.16em;
        }

        h1 {
          margin: 0;
          color: #241d35;
          font-family: Georgia, 'Times New Roman', serif;
          font-size: 22px;
          letter-spacing: -0.02em;
        }

        .chat-heading-note {
          color: #8a8298;
          font-size: 12px;
        }
      }
    }

    .chat-quota-alert {
      flex: 1;
      min-width: 320px;
    }

    .dataset-connection-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border-color: rgba(112, 74, 198, .24);
      color: #704ac6;
      background: rgba(244, 239, 255, .72);
    }

    .message-list {
      flex: 1;
      overflow-y: auto;
      padding: 20px;

      .empty-state {
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: #827a90;

        p {
          margin: 14px 0 0;
          color: #6f667d;
        }

        .quick-prompts {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 8px;
          max-width: 720px;
          margin-top: 18px;
        }

        .quick-prompt {
          border: 1px solid rgba(112, 74, 198, 0.2);
          border-radius: 999px;
          padding: 9px 14px;
          color: #60409d;
          background: rgba(248, 245, 255, 0.86);
          cursor: pointer;
          transition: all 0.2s ease;

          &:hover {
            border-color: rgba(112, 74, 198, 0.42);
            background: rgba(238, 231, 255, 0.96);
            transform: translateY(-1px);
          }
        }
      }

      .message-item {
        margin-bottom: 16px;
        display: flex;

        &.user {
          justify-content: flex-end;
        }

        &.assistant {
          justify-content: flex-start;
        }

        .message-content {
          max-width: 70%;
          padding: 12px 16px;
          border-radius: 12px;
          background: rgba(255, 255, 255, 0.9);
          border: 1px solid rgba(148, 163, 184, 0.2);
          box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
        }

        &.user .message-content {
          background: linear-gradient(135deg, #704ac6 0%, #8b62d9 100%);
          color: white;
          border-color: transparent;
        }

        .message-text {
          white-space: pre-wrap;
          word-break: break-word;
          line-height: 1.6;
        }

        .retrieved-docs {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #e4e7ed;

          .doc-item {
            margin-bottom: 8px;
            padding: 8px;
            background: #f5f7fa;
            border-radius: 4px;

            .doc-meta {
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
              margin-bottom: 6px;
              font-size: 12px;
              color: #606266;

              .doc-book,
              .doc-chapter {
                font-weight: 600;
              }
            }

            .doc-score {
              font-size: 12px;
              color: #827a90;
              margin-bottom: 4px;
            }

            .doc-content {
              font-size: 13px;
              color: #606266;
              line-height: 1.5;
            }
          }
        }
      }

      .streaming-indicator {
        padding: 20px;
        display: flex;
        justify-content: center;
      }
    }

    .input-area {
      padding: 16px;
      background: rgba(255, 255, 255, 0.82);
      border-top: 1px solid rgba(148, 163, 184, 0.2);
      display: flex;
      gap: 12px;
      align-items: flex-end;

      .el-textarea {
        flex: 1;
      }
    }
  }
}

:global(html.dark) .chat-view {
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.78);
}

:global(html.dark) .chat-view .sidebar {
  background: rgba(30, 41, 59, 0.84);
  border-right-color: rgba(148, 163, 184, 0.18);
}

:global(html.dark) .chat-view .chat-container {
  background: rgba(15, 23, 42, 0.62);
}

:global(html.dark) .chat-view .chat-container .chat-header,
:global(html.dark) .chat-view .chat-container .input-area {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(148, 163, 184, 0.18);
}

:global(html.dark) .chat-view .message-item.assistant .message-content {
  background: rgba(30, 41, 59, 0.88);
  border-color: rgba(148, 163, 184, 0.22);
}
</style>
