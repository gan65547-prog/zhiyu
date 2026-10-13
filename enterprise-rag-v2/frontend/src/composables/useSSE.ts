import { ref } from 'vue'

export function useSSE() {
  const eventSource = ref<EventSource | null>(null)
  const connected = ref(false)
  const error = ref<Error | null>(null)

  function connect(
    url: string,
    onMessage: (data: any) => void,
    onError?: (error: Error) => void
  ) {
    disconnect()

    eventSource.value = new EventSource(url)

    eventSource.value.onopen = () => {
      connected.value = true
      error.value = null
    }

    eventSource.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (e) {
        onMessage(event.data)
      }
    }

    eventSource.value.onerror = () => {
      error.value = new Error('SSE connection error')
      connected.value = false
      onError?.(error.value)
    }
  }

  function disconnect() {
    eventSource.value?.close()
    eventSource.value = null
    connected.value = false
    error.value = null
  }

  return {
    connected,
    error,
    connect,
    disconnect
  }
}
