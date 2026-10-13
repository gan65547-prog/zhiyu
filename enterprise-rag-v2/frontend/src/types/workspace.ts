export interface Workspace {
  id: string
  name: string
  description?: string
  is_default: boolean
  created_at: string
  updated_at: string
  dataset_count?: number
  member_count?: number
}

export interface WorkspaceCreate {
  name: string
  description?: string
}

export interface WorkspaceUpdate {
  name?: string
  description?: string
}

export interface WorkspaceState {
  workspaces: Workspace[]
  currentWorkspace: Workspace | null
  loading: boolean
  error: string | null
}

export type WorkspaceRole = 'owner' | 'admin' | 'member' | 'viewer'

export interface WorkspaceMember {
  id: string
  workspace_id: string
  user_id: string
  role: WorkspaceRole
  user?: {
    id: string
    username: string
    email: string
  }
  created_at: string
}

export interface WorkspaceMemberAdd {
  user_id: string
  role: WorkspaceRole
}

export interface WorkspaceMemberUpdate {
  role: WorkspaceRole
}
