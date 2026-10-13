export interface DatasetConfig {
  embedding_model: string
  retrieval_model: string
  chunk_size: number
  chunk_overlap: number
}

export interface DatasetStatistics {
  total_documents: number
  indexed_documents: number
  failed_documents: number
  pending_documents: number
}

export interface Dataset {
  id: string
  user_id?: string
  name: string
  description: string
  document_count: number
  segment_count?: number
  config: DatasetConfig | Record<string, any>
  statistics?: DatasetStatistics
  permission?: string
  indexing_technique?: string
  created_at: string
  updated_at: string
}

export interface DatasetListResponse {
  items: Dataset[]
  total: number
  page: number
  page_size: number
}

export interface CreateDatasetForm {
  name: string
  description?: string
  config?: Partial<DatasetConfig>
}

export interface UpdateDatasetForm {
  name?: string
  description?: string
  config?: Partial<DatasetConfig>
}
