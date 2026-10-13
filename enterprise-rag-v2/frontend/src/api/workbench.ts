import request from './request'

export interface WorkbenchSearchItem {
  id: string
  kind: string
  title: string
  snippet: string
  route: string
  created_at?: string | null
  metadata: Record<string, unknown>
}

export interface WorkbenchTask {
  id: string
  kind: string
  title: string
  status: string
  priority: number
  route: string
  created_at?: string | null
  metadata: Record<string, unknown>
}

export const workbenchApi = {
  search: (workspaceId: string, query: string, limit = 20) => request.get<any, { items: WorkbenchSearchItem[]; total: number; query: string }>('/api/v1/workbench/search', { params: { workspace_id: workspaceId, q: query, limit } }),
  listTasks: (workspaceId: string, limit = 100, includeHistory = false) => request.get<any, { items: WorkbenchTask[]; total: number }>('/api/v1/workbench/tasks', { params: { workspace_id: workspaceId, limit, include_history: includeHistory } })
}
