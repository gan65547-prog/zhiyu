import { ref, computed } from 'vue'
import { chat, chatStream } from '@/api/chat'
import type { Message, Source } from '@/types'

export function useChat() {
  const messages = ref<Message[]>([])
  const loading = ref(false)
  const streaming = ref(false)

  const isEmpty = computed(() => messages.value.length === 0)

  async function send(content: string, datasetId: string, conversationId?: string) {
    loading.value = true

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      created_at: new Date().toISOString()
    }
    messages.value.push(userMessage)

    try {
      const res = await chat({
        query: content,
        dataset_id: datasetId,
        conversation_id: conversationId,
        stream: false
      })

      messages.value.push({
        id: res.data.message_id,
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources,
        created_at: new Date().toISOString()
      })

      return res.data
    } finally {
      loading.value = false
    }
  }

  async function sendStream(
    content: string,
    datasetId: string,
    conversationId?: string
  ) {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      created_at: new Date().toISOString()
    }
    messages.value.push(userMessage)

    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      sources: [],
      created_at: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

    streaming.value = true

    try {
      await chatStream(
        {
          query: content,
          dataset_id: datasetId,
          conversation_id: conversationId,
          stream: true
        },
        (chunk: string) => {
          assistantMessage.content += chunk
        },
        (sources: Source[]) => {
          assistantMessage.sources = sources
        },
        (info: any) => {
          if (info?.message_id) {
            assistantMessage.id = info.message_id
          }
        }
      )
    } finally {
      streaming.value = false
    }
  }

  function clear() {
    messages.value = []
  }

  return {
    messages,
    loading,
    streaming,
    isEmpty,
    send,
    sendStream,
    clear
  }
}
