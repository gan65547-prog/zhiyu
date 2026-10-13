import request from './request'
import type { 
  UserCreate, 
  UserUpdate, 
  UserResetPassword, 
  UserActivate,
  UserListParams
} from '@/types/user'

export const userApi = {
  /**
   * 获取用户列表
   */
  list: async (params?: UserListParams) => {
    const response = await request.get<any>('/api/v1/users', { params })
    return { 
      items: response.data || [], 
      total: response.total || 0,
      page: response.page || 1,
      page_size: response.page_size || 20
    }
  },

  /**
   * 获取用户详情
   */
  get: async (userId: string) => {
    const response = await request.get<any>(`/api/v1/users/${userId}`)
    return response?.data || null
  },

  /**
   * 创建用户
   */
  create: async (data: UserCreate & { tenant_id?: string }) => {
    const { tenant_id, ...userData } = data
    const params = tenant_id ? { tenant_id } : undefined
    const response = await request.post<any>('/api/v1/users', userData, { params })
    return response?.data || null
  },

  /**
   * 更新用户
   */
  update: async (userId: string, data: UserUpdate) => {
    const response = await request.put<any>(`/api/v1/users/${userId}`, data)
    return response?.data || null
  },

  /**
   * 删除用户
   */
  delete: async (userId: string) => {
    await request.delete(`/api/v1/users/${userId}`)
  },

  /**
   * 重置用户密码
   */
  resetPassword: async (userId: string, data: UserResetPassword) => {
    const response = await request.post<any>(`/api/v1/users/${userId}/reset-password`, data)
    return response?.data || null
  },

  /**
   * 激活/停用用户
   */
  activate: async (userId: string, data: UserActivate) => {
    const response = await request.put<any>(`/api/v1/users/${userId}/activate`, data)
    return response?.data || null
  },

  /**
   * 获取用户的工作空间列表
   */
  getWorkspaces: async (userId: string) => {
    const response = await request.get<any>(`/api/v1/users/${userId}/workspaces`)
    return response?.data || []
  }
}
