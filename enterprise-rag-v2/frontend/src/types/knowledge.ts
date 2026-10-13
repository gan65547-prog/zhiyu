export type KnowledgeReviewStatus = 'draft' | 'approved' | 'rejected'

export interface KnowledgeEvidence {
  id: string
  knowledge_item_id: string
  asset_id?: string | null
  document_id?: string | null
  chunk_id?: string | null
  quote: string
  locator?: string | null
  source_uri?: string | null
  created_by: string
  created_at: string
}

export interface KnowledgeItem {
  id: string
  tenant_id: string
  workspace_id: string
  created_by: string
  title: string
  item_type: string
  definition: string
  details?: string | null
  conclusions: string[]
  confidence: number
  review_status: KnowledgeReviewStatus
  reviewer_id?: string | null
  reviewed_at?: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
  evidence: KnowledgeEvidence[]
}

export interface KnowledgeItemListResponse {
  items: KnowledgeItem[]
  total: number
  page: number
  page_size: number
}

export interface KnowledgeItemVersion {
  id: string
  knowledge_item_id: string
  version: number
  title: string
  item_type: string
  definition: string
  details?: string | null
  conclusions: string[]
  confidence: number
  metadata: Record<string, unknown>
  created_by: string
  created_at: string
}
