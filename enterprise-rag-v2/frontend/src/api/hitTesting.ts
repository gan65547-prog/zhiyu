import request from './request'
import type { ApiResponse } from '@/types'

export interface HitTestingRecord {
  segment_id: string
  document_id: string
  document_name: string
  content: string
  score: number
  rerank_score?: number
}

export interface HitTestingResponse {
  query: string
  records: HitTestingRecord[]
  total: number
}

export const hitTesting = (
  datasetId: string,
  data: {
    query: string
    top_k?: number
    search_method?: 'semantic' | 'full_text' | 'hybrid'
  }
) => {
  return request.post<any, ApiResponse<HitTestingResponse>>(
    `/datasets/${datasetId}/hit-testing`,
    data
  )
}
