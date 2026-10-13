import request from './request'
import type { UpdateDatasetForm } from '@/types'

export const getDatasets = (params?: { page?: number; page_size?: number; workspace_id?: string; include_public?: boolean }) => {
  return request.get<any, any>('/api/v1/datasets/', { params }).then(res => {
    console.log('getDatasets raw response:', res)
    console.log('getDatasets res structure:', Object.keys(res))
    const result = res.data?.data || res.data || res
    console.log('getDatasets processed result:', result)
    if (Array.isArray(result)) {
      console.log('getDatasets result is array, length:', result.length)
    } else if (result) {
      console.log('getDatasets result structure:', Object.keys(result))
    }
    return result
  })
}

export const getDataset = (id: string) => {
  return request.get<any, any>(`/api/v1/datasets/${id}`).then(res => res.data?.data || res.data)
}

export const createDataset = (data: any) => {
  const backendData: Record<string, unknown> = {
    name: data.name,
    description: data.description,
    embedding_model: data.config?.embedding_model || 'bge-small-zh-v1.5',
    chunk_size: data.config?.chunk_size || 500,
    chunk_overlap: data.config?.chunk_overlap || 50
  }
  // 保留workspace_id字段
  if (data.workspace_id) {
    backendData.workspace_id = data.workspace_id
  }
  return request.post<any, any>('/api/v1/datasets/', backendData).then(res => res.data?.data || res.data)
}

export const updateDataset = (id: string, data: UpdateDatasetForm) => {
  return request.put<any, any>(`/api/v1/datasets/${id}`, data).then(res => res.data?.data || res.data)
}

export const deleteDataset = (id: string) => {
  return request.delete<any, any>(`/api/v1/datasets/${id}`)
}

export const hitTesting = (
  datasetId: string,
  data: { query: string; top_k?: number; search_method?: string }
) => {
  return request.post<any, any>(`/api/v1/datasets/${datasetId}/hit-testing`, data).then(res => res.data?.data || res.data)
}
