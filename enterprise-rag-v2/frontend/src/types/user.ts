/**
 * 用户管理类型定义
 */

import type { WorkspaceRole } from './workspace'

export interface User {
  id: string
  username: string
  email: string
  is_active: boolean
  is_superuser: boolean
  is_tenant_admin?: boolean
  tenant_id: string
  current_workspace_id?: string | null
  created_at: string
  updated_at: string
}

export interface UserDetail extends User {
  tenant_name?: string
  current_workspace_name?: string
  workspaces?: UserWorkspace[]
  extra_metadata?: Record<string, any>
  last_login_at?: string
}

export interface UserWorkspace {
  workspace_id: string
  workspace_name: string
  role: WorkspaceRole
  is_default?: boolean
  joined_at?: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  is_active?: boolean
  workspace_ids?: string[]
  default_role?: WorkspaceRole
}

export interface UserUpdate {
  username?: string
  email?: string
  is_active?: boolean
  workspace_ids?: string[]
  default_role?: WorkspaceRole
}

export interface UserResetPassword {
  new_password: string
  send_email?: boolean
}

export interface UserActivate {
  is_active: boolean
}

export interface UserListParams {
  page?: number
  page_size?: number
  search?: string
  is_active?: boolean
  workspace_id?: string
  tenant_id?: string
}
