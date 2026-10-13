export interface Source {
  document_id?: string
  document_name?: string
  segment_id?: string
  content: string
  score: number
  chapter?: string
  metadata?: Record<string, any>
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  created_at: string
}

export interface ChatRequest {
  query: string
  dataset_id: string
  conversation_id?: string
  stream?: boolean
  history?: Message[]
}

export interface ConversationCreate {
  dataset_id: string
  title?: string
}

export interface ConversationUpdate {
  title?: string
}

export interface ChatResponse {
  answer: string
  sources: Source[]
  conversation_id: string
  message_id: string
}

export interface Conversation {
  id: string
  dataset_id: string
  title: string
  metadata: any
  created_at: string
  updated_at: string
}

export interface ConversationListResponse {
  items: Conversation[]
  total: number
  page: number
  page_size: number
}

export interface MessageListResponse {
  items: Message[]
  total: number
  page: number
  page_size: number
}
