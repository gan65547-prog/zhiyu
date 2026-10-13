export interface Document {
  id: string
  dataset_id: string
  name: string
  size: number
  type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  processing_phase?: 'extracting' | 'chunking' | 'embedding' | 'indexing' | 'completed' | 'failed' | string
  done_chunks?: number
  total_chunks?: number
  segment_count: number
  /** 处理失败时的后端错误摘要（仅 status=failed 时可能有值） */
  error_reason?: string | null
  position: number
  indexing_time?: number
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  items: Document[]
  total: number
  page: number
  page_size: number
}

export interface UploadDocumentResponse {
  document: Document
  task_id: string
}

export interface ProcessRule {
  mode: 'automatic' | 'custom'
  rules?: {
    chunk_size: number
    chunk_overlap: number
  }
}

export interface Segment {
  id: string
  content: string
  word_count: number
  index_node_id: string
  position: number
  created_at: string
}

export interface SegmentListResponse {
  items: Segment[]
  total: number
  page: number
  page_size: number
}
