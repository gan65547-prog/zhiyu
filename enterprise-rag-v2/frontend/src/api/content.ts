import request from './request'
import type { ContentCredential, ContentDraft, ContentMetricSyncRun, ContentPublishRecord, ContentRetrospective, ContentTopic } from '@/types/content'

export const contentApi = {
  listConnectors: () => request.get<any, Array<{ key: string; label: string; status: string; requires_credentials?: boolean; supports_metric_sync?: boolean }>>('/api/v1/content/connectors'),
  listTopics: (workspaceId: string) => request.get<any, { items: ContentTopic[]; total: number }>('/api/v1/content/topics', { params: { workspace_id: workspaceId } }),
  createTopic: (payload: { workspace_id: string; title: string; brief?: string; tags?: string[] }) => request.post<any, ContentTopic>('/api/v1/content/topics', payload),
  listDrafts: (workspaceId: string) => request.get<any, { items: ContentDraft[]; total: number }>('/api/v1/content/drafts', { params: { workspace_id: workspaceId } }),
  listPublishes: (workspaceId: string) => request.get<any, { items: ContentPublishRecord[]; total: number }>('/api/v1/content/publishes', { params: { workspace_id: workspaceId } }),
  listMetrics: (workspaceId: string) => request.get<any, { items: Array<{ id: string; publish_record_id: string; workspace_id: string; platform: string; published_at: string; collected_at: string; impressions: number; clicks: number; likes: number; comments: number; shares: number }>; total: number }>('/api/v1/content/publishes/metrics', { params: { workspace_id: workspaceId, limit: 500 } }),
  createDraft: (payload: { workspace_id: string; topic_id?: string; title: string; body: string }) => request.post<any, ContentDraft>('/api/v1/content/drafts', payload),
  updateDraft: (draftId: string, payload: { topic_id?: string | null; title?: string; body?: string }) => request.put<any, ContentDraft>(`/api/v1/content/drafts/${draftId}`, payload),
  rewriteDraft: (draftId: string, platforms: string[], mode: 'deterministic' | 'model' = 'deterministic') => request.post<any, ContentDraft>(`/api/v1/content/drafts/${draftId}/rewrite`, { platforms, mode }),
  createDraftFromResearch: (reportId: string, payload: { topic_id?: string; title?: string } = {}) => request.post<any, ContentDraft>(`/api/v1/content/drafts/from-research/${reportId}`, payload),
  reviewDraft: (draftId: string, status: 'approved' | 'rejected') => request.post<any, ContentDraft>(`/api/v1/content/drafts/${draftId}/review`, { status }),
  publishDraft: (draftId: string, platform: string, external_id?: string, credential_id?: string) => request.post<any, ContentPublishRecord>(`/api/v1/content/drafts/${draftId}/publish`, { platform, external_id, credential_id }),
  scheduleDraft: (draftId: string, platform: string, scheduled_at: string, credential_id?: string) => request.post<any, ContentPublishRecord>(`/api/v1/content/drafts/${draftId}/schedule`, { platform, scheduled_at, credential_id }),
  confirmPublish: (publishId: string, external_id?: string) => request.post<any, ContentPublishRecord>(`/api/v1/content/publishes/${publishId}/confirm`, { external_id }),
  createRetrospective: (publishId: string) => request.post<any, ContentRetrospective>(`/api/v1/content/publishes/${publishId}/retrospective`),
  getRetrospective: (publishId: string) => request.get<any, ContentRetrospective>(`/api/v1/content/publishes/${publishId}/retrospective`),
  addMetric: (publishId: string, payload: Record<string, number>) => request.post<any, ContentPublishRecord>(`/api/v1/content/publishes/${publishId}/metrics`, payload)
  ,importMetrics: (payload: { workspace_id: string; items: Array<{ publish_id: string; collected_at: string; metric: Record<string, unknown> }> }) => request.post<any, { workspace_id: string; inserted: number; skipped: number }>('/api/v1/content/publishes/metrics/import', payload)
  ,createMetricSync: (payload: { workspace_id: string; platform: string; credential_id?: string; items?: Array<{ publish_id: string; collected_at: string; metric: Record<string, unknown> }> }) => request.post<any, ContentMetricSyncRun>('/api/v1/content/publishes/metrics/sync', payload)
  ,listMetricSync: (workspaceId: string) => request.get<any, { items: ContentMetricSyncRun[]; total: number }>('/api/v1/content/publishes/metrics/sync', { params: { workspace_id: workspaceId } })
  ,getMetricSync: (runId: string) => request.get<any, ContentMetricSyncRun>(`/api/v1/content/publishes/metrics/sync/${runId}`)
  ,retryMetricSync: (runId: string) => request.post<any, ContentMetricSyncRun>(`/api/v1/content/publishes/metrics/sync/${runId}/retry`)
  ,listCredentials: (workspaceId: string) => request.get<any, ContentCredential[]>('/api/v1/content/credentials', { params: { workspace_id: workspaceId } })
  ,createCredential: (payload: { workspace_id: string; platform: string; name: string; credentials: Record<string, string>; credential_hint?: string }) => request.post<any, ContentCredential>('/api/v1/content/credentials', payload)
  ,revokeCredential: (credentialId: string) => request.delete<any, ContentCredential>(`/api/v1/content/credentials/${credentialId}`)
  ,testCredential: (credentialId: string, workspaceId: string) => request.post<any, { credential_id: string; platform: string; status: string; message: string; connector_registered: boolean; checked_at: string }>(`/api/v1/content/credentials/${credentialId}/test`, null, { params: { workspace_id: workspaceId } })
  ,startXOAuth: (workspaceId: string) => request.get<any, { url: string }>('/api/v1/content/oauth/x/start', { params: { workspace_id: workspaceId } })
  ,completeXOAuth: (payload: { code: string; state: string }) => request.post<any, { credential: ContentCredential; provider_user_id: string }>('/api/v1/content/oauth/x/complete', payload)
}
