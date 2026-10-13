import request from './request'
import type { WorkspaceCreate, WorkspaceUpdate, WorkspaceMember, WorkspaceMemberAdd, WorkspaceMemberUpdate } from '@/types/workspace'

const normalizeWorkspaceRole = (role: unknown): WorkspaceMember['role'] => {
  const normalized = String(role || '').toLowerCase()
  if (normalized === 'owner' || normalized === 'admin' || normalized === 'viewer') {
    return normalized
  }
  return 'member'
}

export const workspaceApi = {
  list: async (params?: { tenant_id?: string; page?: number; page_size?: number }) => {
    const response = await request.get<any>('/api/v1/workspaces/', { params })
    return { items: response?.data || [], total: response?.total || 0 }
  },

  get: async (id: string) => {
    const response = await request.get<any>(`/api/v1/workspaces/${id}`)
    return response?.data || null
  },

  create: async (data: WorkspaceCreate) => {
    const response = await request.post<any>('/api/v1/workspaces/', data)
    return response?.data || null
  },

  update: async (id: string, data: WorkspaceUpdate) => {
    const response = await request.put<any>(`/api/v1/workspaces/${id}`, data)
    return response?.data || null
  },

  switch: async (id: string) => {
    const response = await request.post<any>(`/api/v1/workspaces/${id}/switch`)
    return response?.data || null
  },

  getCurrent: async () => {
    const response = await request.get<any>('/api/v1/workspaces/current', {
      skipGlobalErrorHandler: true
    } as any)
    return response?.data || null
  },

  // 成员管理相关API
  listMembers: async (workspaceId: string) => {
    console.log('Calling listMembers for workspace:', workspaceId)
    try {
      const response = await request.get<any>(`/api/v1/workspaces/${workspaceId}/members`)
      console.log('listMembers response:', response)
      const members = Array.isArray(response?.data) ? response.data : []
      return members.map((member: WorkspaceMember) => ({
        ...member,
        role: normalizeWorkspaceRole(member?.role)
      }))
    } catch (error) {
      console.warn('Failed to fetch workspace members:', error)
      return []
    }
  },

  addMember: async (workspaceId: string, data: WorkspaceMemberAdd) => {
    const response = await request.post<any>(`/api/v1/workspaces/${workspaceId}/members`, data)
    return response?.data || null
  },

  updateMember: async (workspaceId: string, userId: string, data: WorkspaceMemberUpdate) => {
    const response = await request.put<any>(`/api/v1/workspaces/${workspaceId}/members/${userId}`, data)
    return response?.data || null
  },

  removeMember: async (workspaceId: string, userId: string) => {
    await request.delete(`/api/v1/workspaces/${workspaceId}/members/${userId}`)
  },

  delete: async (id: string) => {
    const response = await request.delete<any>(`/api/v1/workspaces/${id}`)
    return response?.data || null
  }
}

// 导出便捷函数
export const getWorkspaceList = (params?: { tenant_id?: string; page?: number; page_size?: number }) => {
  return request.get<any>('/api/v1/workspaces/', { params })
}
