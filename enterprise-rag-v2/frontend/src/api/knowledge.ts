import request from './request'
import type { KnowledgeEvidence, KnowledgeItem, KnowledgeItemListResponse, KnowledgeItemVersion, KnowledgeReviewStatus } from '@/types/knowledge'

export interface CreateKnowledgeItemPayload {
  workspace_id: string
  title: string
  item_type: string
  definition: string
  details?: string
  conclusions?: string[]
  confidence?: number
  metadata?: Record<string, unknown>
}

export const knowledgeApi = {
  list: (workspaceId: string, status?: KnowledgeReviewStatus) => request.get<any, KnowledgeItemListResponse>('/api/v1/knowledge/items', { params: { workspace_id: workspaceId, status, page: 1, page_size: 100 } }),
  create: (payload: CreateKnowledgeItemPayload) => request.post<any, KnowledgeItem>('/api/v1/knowledge/items', payload),
  update: (id: string, payload: Partial<CreateKnowledgeItemPayload>) => request.patch<any, KnowledgeItem>(`/api/v1/knowledge/items/${id}`, payload),
  review: (id: string, status: KnowledgeReviewStatus) => request.post<any, KnowledgeItem>(`/api/v1/knowledge/items/${id}/review`, { status }),
  addEvidence: (id: string, payload: { asset_id?: string; document_id?: string; chunk_id?: string; quote: string; locator?: string; source_uri?: string }) => request.post<any, KnowledgeEvidence>(`/api/v1/knowledge/items/${id}/evidence`, payload),
  versions: (id: string) => request.get<any, KnowledgeItemVersion[]>(`/api/v1/knowledge/items/${id}/versions`),
  rollback: (id: string, versionId: string) => request.post<any, KnowledgeItem>(`/api/v1/knowledge/items/${id}/versions/${versionId}/rollback`)
}

export interface KnowledgeNetworkNode {
  id: string
  title: string
  item_type: string
  confidence: number
}

export interface KnowledgeNetworkEdge {
  id: string
  workspace_id: string
  source_item_id: string
  target_item_id: string
  source_title: string
  target_title: string
  relation_type: string
  description?: string | null
  created_by?: string | null
  created_at: string
}

export interface KnowledgeRelationSuggestion {
  source_item_id: string
  target_item_id: string
  source_title: string
  target_title: string
  relation_type: string
  score: number
  matched_terms: string[]
  requires_human_review: boolean
  description?: string
  origin?: 'rules' | 'model'
}

export const knowledgeNetworkApi = {
  network: (workspaceId: string) => request.get<any, { nodes: KnowledgeNetworkNode[]; edges: KnowledgeNetworkEdge[] }>('/api/v1/knowledge/relations/network', { params: { workspace_id: workspaceId } }),
  suggestions: (workspaceId: string) => request.get<any, KnowledgeRelationSuggestion[]>('/api/v1/knowledge/relations/suggestions', { params: { workspace_id: workspaceId } }),
  modelSuggestions: (workspaceId: string, provider?: string) => request.get<any, KnowledgeRelationSuggestion[]>('/api/v1/knowledge/relations/suggestions/model', { params: { workspace_id: workspaceId, provider } }),
  batchReview: (workspaceId: string, relations: Array<{ source_item_id: string; target_item_id: string; relation_type: string; description?: string }>) => request.post<any, KnowledgeNetworkEdge[]>('/api/v1/knowledge/relations/suggestions/batch-review', { relations }, { params: { workspace_id: workspaceId } }),
  create: (workspaceId: string, data: { source_item_id: string; target_item_id: string; relation_type: string; description?: string }) => request.post<any, KnowledgeNetworkEdge>('/api/v1/knowledge/relations', data, { params: { workspace_id: workspaceId } }),
  remove: (workspaceId: string, relationId: string) => request.delete(`/api/v1/knowledge/relations/${relationId}`, { params: { workspace_id: workspaceId } })
}
