import request from './request'
import type {
  Document,
  DocumentListResponse,
  UploadDocumentResponse,
  SegmentListResponse,
  ProcessRule,
  ApiResponse
} from '@/types'

/** 避免 route.params / 变量未赋值时把 `undefined` 拼进 URL 触发海量 500 与 Toast */
export function isValidDatasetIdForApi(
  id: string | undefined | null
): id is string {
  if (id == null) return false
  const s = String(id).trim()
  if (!s) return false
  const lower = s.toLowerCase()
  if (lower === 'undefined' || lower === 'null') return false
  return true
}

export const getDocuments = (
  datasetId: string,
  params?: { page?: number; page_size?: number; status?: string; keyword?: string }
) => {
  if (!isValidDatasetIdForApi(datasetId)) {
    return Promise.reject(new Error('INVALID_DATASET_ID'))
  }
  return request.get<any, ApiResponse<DocumentListResponse>>(
    `/api/v1/documents/datasets/${datasetId}`,
    { params }
  )
}

export const getDocument = (id: string) => {
  return request.get<any, ApiResponse<Document>>(`/api/v1/documents/${id}`)
}

function normalizeDatasetIdForPath(id: string): string {
  return String(id).trim().replace(/^\/+|\/+$/g, '')
}

export const uploadDocument = (
  datasetId: string,
  file: File,
  processRule?: ProcessRule
) => {
  const formData = new FormData()
  formData.append('file', file)
  if (processRule) {
    formData.append('process_rule', JSON.stringify(processRule))
  }

  if (!isValidDatasetIdForApi(datasetId)) {
    return Promise.reject(new Error('INVALID_DATASET_ID'))
  }
  const id = normalizeDatasetIdForPath(datasetId)
  const url = `/api/v1/documents/datasets/${id}`
  
  return request.post<any, ApiResponse<UploadDocumentResponse>>(
    url,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 60000,
      maxRedirects: 0
    }
  )
}

export interface UploadRetryOptions {
  maxRetries?: number
  baseDelay?: number
  onRetry?: (attempt: number, error: Error) => void
}

export const uploadDocumentWithRetry = async (
  datasetId: string,
  file: File,
  processRule?: ProcessRule,
  options?: UploadRetryOptions
): Promise<ApiResponse<UploadDocumentResponse>> => {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    onRetry
  } = options || {}

  let lastError: Error | null = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0 && onRetry) {
        onRetry(attempt, lastError!)
      }

      const result = await uploadDocument(datasetId, file, processRule)

      const responseMeta = result as unknown as { data?: { code?: number }; status?: number }
      if (responseMeta.data?.code === 429 || responseMeta.status === 429) {
        throw new Error('Rate limit exceeded')
      }

      return result
    } catch (error: any) {
      lastError = error

      const isNetworkError = !error.response || error.code === 'ERR_NETWORK' || error.message?.includes('Network') || error.message?.includes('Connection')
      const isServerError = error.response?.status >= 500
      const isClientError = error.response?.status >= 400 && error.response?.status < 500
      
      if (!isNetworkError && !isServerError || attempt === maxRetries || isClientError) {
        throw error
      }

      const delay = baseDelay * Math.pow(2, attempt - 1)
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }

  throw lastError
}

export function createConcurrentUploader(concurrency: number = 3) {
  let activeCount = 0
  const queue: Array<() => Promise<void>> = []

  const runNext = async () => {
    if (queue.length === 0 || activeCount >= concurrency) return

    activeCount++
    const task = queue.shift()!
    try {
      await task()
    } finally {
      activeCount--
      runNext()
    }
  }

  return {
    add<T>(task: () => Promise<T>): Promise<T> {
      return new Promise((resolve, reject) => {
        queue.push(async () => {
          try {
            resolve(await task())
          } catch (error) {
            reject(error)
          }
        })
        runNext()
      })
    },

    waitForAll(): Promise<void> {
      return new Promise(resolve => {
        const check = () => {
          if (activeCount === 0 && queue.length === 0) {
            resolve()
          } else {
            setTimeout(check, 100)
          }
        }
        check()
      })
    }
  }
}

export const deleteDocument = (id: string) => {
  return request.delete<any, ApiResponse<null>>(`/api/v1/documents/${id}`)
}

export const getDocumentSegments = (
  docId: string,
  params?: { page?: number; page_size?: number }
) => {
  return request.get<any, ApiResponse<SegmentListResponse>>(
    `/api/v1/documents/${docId}/segments`,
    { params }
  )
}

/** 读取文档原文（后端优先解析源文件，否则拼接已索引分段） */
export async function getDocumentFullText(docId: string): Promise<string> {
  const res = await request.get<any, ApiResponse<{ text: string }> & { text?: string }>(
    `/api/v1/documents/${docId}/original-text`
  )
  const payload = res?.data ?? res
  if (payload && typeof payload === 'object' && typeof (payload as { text?: string }).text === 'string') {
    return (payload as { text: string }).text
  }
  return ''
}

export const importWechatChat = (
  datasetId: string,
  file: File,
  chatName?: string
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('dataset_id', datasetId)
  if (chatName) {
    formData.append('chat_name', chatName)
  }

  if (!isValidDatasetIdForApi(datasetId)) {
    return Promise.reject(new Error('INVALID_DATASET_ID'))
  }

  return request.post<any, ApiResponse<{
    document_id: string
    file_name: string
    total_messages: number
    participants: string[]
    date_range: [string, string]
    format_detected: string
  }>>(
    '/api/v1/documents/import/wechat',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000
    }
  )
}

export const updateSegment = (
  docId: string,
  segmentId: string,
  data: { content: string }
) => {
  return request.put<any, ApiResponse<any>>(
    `/api/v1/documents/${docId}/segments/${segmentId}`,
    data
  )
}
