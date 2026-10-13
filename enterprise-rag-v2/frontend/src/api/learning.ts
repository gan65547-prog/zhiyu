import request from './request'
import type { ApiResponse } from '@/types'
import type {
  LearningDiagnosisRequest,
  LearningDiagnosisReport,
  LearningDiagnosisReportListItem,
  LearningDiagnosisFeedback,
  PracticeSession,
  PracticeAnswerResult,
} from '@/types/learning'

export const learningApi = {
  analyze: (data: LearningDiagnosisRequest) =>
    request.post<any, ApiResponse<LearningDiagnosisReport>>('/api/v1/learning/analyze', data),

  analyzeStream: (data: LearningDiagnosisRequest): EventSource => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    const url = `${baseUrl}/api/v1/learning/analyze/stream`
    const token = localStorage.getItem('access_token') || ''
    const controller = new AbortController()

    const eventSource = {
      close: () => controller.abort(),
      controller,
      async *read() {
        const csrfToken = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)?.[1] || ''
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify(data),
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('event:') || line.startsWith('data:')) {
              yield line
            }
          }
        }
      },
    }
    return eventSource as any
  },

  listReports: (params?: { page?: number; page_size?: number }) =>
    request.get<any, ApiResponse<{ items: LearningDiagnosisReportListItem[]; total: number }>>('/api/v1/learning/reports', { params }),

  getReport: (id: string) =>
    request.get<any, ApiResponse<LearningDiagnosisReport>>(`/api/v1/learning/reports/${id}`),

  submitFeedback: (data: LearningDiagnosisFeedback) =>
    request.post<any, ApiResponse>('/api/v1/learning/feedback', data),

  startPractice: (reportId: string) =>
    request.post<any, ApiResponse<PracticeSession>>(`/api/v1/learning/reports/${reportId}/start-practice`),

  getPracticeSession: (sessionId: string) =>
    request.get<any, ApiResponse<PracticeSession>>(`/api/v1/learning/practice/${sessionId}`),

  submitPracticeAnswer: (sessionId: string, data: { exercise_idx: number; answer: string }) =>
    request.post<any, ApiResponse<PracticeAnswerResult>>(`/api/v1/learning/practice/${sessionId}/submit`, data),
}
