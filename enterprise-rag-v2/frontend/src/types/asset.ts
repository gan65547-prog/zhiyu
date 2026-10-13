export type AssetSourceType = 'file' | 'url' | 'text' | 'chat'
export type AssetStatus = 'pending' | 'processing' | 'ready' | 'failed' | 'deleted'

export interface Asset {
  id: string
  tenant_id: string
  workspace_id: string
  dataset_id?: string | null
  batch_id?: string | null
  created_by: string
  legacy_document_id?: string | null
  source_type: AssetSourceType
  title: string
  source_uri?: string | null
  storage_key?: string | null
  source_etag?: string | null
  mime_type?: string | null
  size_bytes: number
  content_hash?: string | null
  status: AssetStatus
  progress?: number
  processing_error?: string | null
  metadata?: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
  processed_at?: string | null
  deleted_at?: string | null
}

export interface AssetProcessingStatus {
  asset_id: string
  status: string
  progress: number
  phase?: string | null
  document_id?: string | null
  document_status?: string | null
  done_chunks: number
  total_chunks: number
  stalled?: boolean
  processing_error?: string | null
}

export interface AssetListResponse {
  items: Asset[]
  total: number
  page: number
  page_size: number
}

export interface AssetBatch {
  id: string
  workspace_id: string
  dataset_id: string
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  assets: Asset[]
  created_at?: string | null
  updated_at?: string | null
  completed_at?: string | null
}
