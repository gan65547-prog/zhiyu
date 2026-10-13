import request from './request'
import type { ApiResponse } from '@/types'

export interface Task {
  id: string
  type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  result: any
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export const getTask = (taskId: string) => {
  return request.get<any, ApiResponse<Task>>(`/tasks/${taskId}`)
}
