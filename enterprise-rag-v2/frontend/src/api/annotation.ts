import request from './request'
import type { ApiResponse } from '@/types'
import type { DocumentAnnotation, DocumentAnnotationKind } from '@/types/annotation'

export const annotationApi = {
  list(documentId: string) {
    return request.get<any, { items: DocumentAnnotation[]; total: number }>(`/api/v1/documents/${documentId}/annotations`)
  },
  create(documentId: string, payload: { kind: DocumentAnnotationKind; quote?: string; body: string; question?: string }) {
    return request.post<any, DocumentAnnotation>(`/api/v1/documents/${documentId}/annotations`, payload)
  },
  remove(documentId: string, annotationId: string) {
    return request.delete<any, ApiResponse<null>>(`/api/v1/documents/${documentId}/annotations/${annotationId}`)
  }
}
