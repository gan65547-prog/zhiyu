import request from './request'
import type { Asset, AssetBatch, AssetListResponse, AssetProcessingStatus, AssetSourceType } from '@/types/asset'

export interface CreateAssetPayload {
  workspace_id: string
  dataset_id?: string
  source_type: AssetSourceType
  title: string
  source_uri?: string
}

export const assetApi = {
  importBatch: async (workspaceId: string, files: File[], datasetId?: string) => {
    const formData = new FormData()
    formData.append('workspace_id', workspaceId)
    if (datasetId) formData.append('dataset_id', datasetId)
    files.forEach(file => formData.append('files', file))
    return request.post<any, AssetBatch>('/api/v1/assets/import-batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000
    })
  },
  importUrls: async (workspaceId: string, urls: string[], datasetId?: string) => request.post<any, AssetBatch>('/api/v1/assets/import-urls', { workspace_id: workspaceId, urls, dataset_id: datasetId }),
  list: async (workspaceId: string, params?: { page?: number; page_size?: number; status?: string }) => {
    return request.get<any, AssetListResponse>('/api/v1/assets', {
      params: { workspace_id: workspaceId, ...params }
    })
  },
  create: async (payload: CreateAssetPayload) => request.post<any, Asset>('/api/v1/assets', payload),
  upload: async (assetId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<any, Asset>(`/api/v1/assets/${assetId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000
    })
  },
  ingestText: async (assetId: string, content: string) => request.post<any, Asset>(`/api/v1/assets/${assetId}/text`, { content }),
  ingest: async (assetId: string) => request.post<any, { asset_id: string; status: string; task_id?: string }>(`/api/v1/assets/${assetId}/ingest`),
  processingStatus: async (assetId: string) => request.get<any, AssetProcessingStatus>(`/api/v1/assets/${assetId}/processing-status`),
  getBatch: async (workspaceId: string, batchId: string) => request.get<any, AssetBatch>(`/api/v1/assets/batches/${batchId}`, { params: { workspace_id: workspaceId } }),
  retryBatch: async (workspaceId: string, batchId: string) => request.post<any, AssetBatch>(`/api/v1/assets/batches/${batchId}/retry-failed`, null, { params: { workspace_id: workspaceId } }),
  retry: async (assetId: string) => request.post<any, { asset_id: string; status: string; task_id?: string }>(`/api/v1/assets/${assetId}/retry`),
  organize: async (assetId: string) => request.post<any, { asset_id: string; agent_run_id: string; status: string; task_id?: string }>(`/api/v1/assets/${assetId}/organize`),
  remove: async (assetId: string) => request.delete(`/api/v1/assets/${assetId}`)
}
