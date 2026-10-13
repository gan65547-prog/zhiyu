import request from './request'
import type { ResearchEvidence, ResearchFinding, ResearchProject, ResearchProjectListResponse, ResearchReport, ResearchRun, ResearchRunListResponse } from '@/types/research'

export const researchApi = {
  createConsultation: (payload: { workspace_id: string; question: string; samples?: { asset_id?: string; dataset_id?: string; source_uri?: string }[]; metadata?: Record<string, unknown>; limits?: Record<string, unknown> }) => request.post<any, ResearchRun>('/api/v1/research/consultations', payload),
  listProjects: (workspaceId: string) => request.get<any, ResearchProjectListResponse>('/api/v1/research/projects', { params: { workspace_id: workspaceId, page: 1, page_size: 100 } }),
  createProject: (payload: { workspace_id: string; name: string; description?: string; questions: { question: string; sort_order: number }[]; samples: { asset_id?: string; dataset_id?: string; source_uri?: string }[]; metadata?: Record<string, unknown> }) => request.post<any, ResearchProject>('/api/v1/research/projects', payload),
  listRuns: (projectId: string) => request.get<any, ResearchRunListResponse>(`/api/v1/research/projects/${projectId}/runs`, { params: { page: 1, page_size: 20 } }),
  listEvidence: (projectId: string) => request.get<any, ResearchEvidence[]>(`/api/v1/research/projects/${projectId}/evidence`),
  listFindings: (projectId: string) => request.get<any, ResearchFinding[]>(`/api/v1/research/projects/${projectId}/findings`),
  listRunEvidence: (runId: string) => request.get<any, ResearchEvidence[]>(`/api/v1/research/runs/${runId}/evidence`),
  listRunFindings: (runId: string) => request.get<any, ResearchFinding[]>(`/api/v1/research/runs/${runId}/findings`),
  createRun: (projectId: string) => request.post<any, ResearchRun>(`/api/v1/research/projects/${projectId}/runs`, { limits: {} }),
  cancelRun: (runId: string) => request.post<any, ResearchRun>(`/api/v1/research/runs/${runId}/cancel`),
  retryRun: (runId: string) => request.post<any, ResearchRun>(`/api/v1/research/runs/${runId}/retry`),
  getReport: (runId: string) => request.get<any, ResearchReport>(`/api/v1/research/runs/${runId}/report`),
  reviewReport: (reportId: string, review_status: 'approved' | 'rejected') => request.post<any, ResearchReport>(`/api/v1/research/reports/${reportId}/review`, { review_status }),
  updateReport: (reportId: string, content_markdown: string) => request.put<any, ResearchReport>(`/api/v1/research/reports/${reportId}`, { content_markdown })
  ,publishReport: (reportId: string, dataset_id: string) => request.post<any, ResearchReport>(`/api/v1/research/reports/${reportId}/publish-to-dataset`, { dataset_id })
  ,publishToKnowledge: (reportId: string, title?: string) => request.post<any, ResearchReport>(`/api/v1/research/reports/${reportId}/publish-to-knowledge`, { title })
}
