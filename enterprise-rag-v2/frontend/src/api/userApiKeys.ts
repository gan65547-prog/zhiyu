import request from './request'

export interface UserApiKey {
  id: string
  provider: string
  name: string
  base_url: string
  is_active: boolean
  is_default: boolean
  configured: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface UserApiKeyCreatePayload {
  provider: string
  name: string
  api_key: string
  base_url?: string
  is_default?: boolean
}

export const userApiKeysApi = {
  async list(): Promise<UserApiKey[]> {
    const response = await request.get<{ data: UserApiKey[] }>('/api/v1/auth/me/api-keys')
    return response.data?.data || []
  },

  async create(payload: UserApiKeyCreatePayload): Promise<UserApiKey> {
    const response = await request.post<{ data: UserApiKey }>('/api/v1/auth/me/api-keys', payload)
    return response.data.data
  },

  async remove(id: string): Promise<void> {
    await request.delete(`/api/v1/auth/me/api-keys/${id}`)
  }
}
