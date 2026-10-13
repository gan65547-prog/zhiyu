export type DocumentAnnotationKind = 'note' | 'understanding'

export interface DocumentAnnotation {
  id: string
  document_id: string
  author_id: string
  kind: DocumentAnnotationKind
  quote: string
  body: string
  question?: string | null
  created_at: string
  updated_at: string
}
