import request from './request'

export interface Tenant {
  id: string
  name: string
  contact_email: string
  contact_phone?: string
  status: string
  metadata?: any
  created_at: string
  updated_at: string
  admin_info?: {
    username: string
    email: string
  }
}

export interface TenantCreate {
  name: string
  contact_email: string
  contact_phone?: string
  metadata?: any
  admin_username: string
  admin_email: string
  admin_password: string
}

export interface TenantUpdate {
  name?: string
  contact_email?: string
  contact_phone?: string
  status?: string
  metadata?: any
}

// 租户列表（仅管理员）
export function getTenantList(params?: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request({
    url: '/api/v1/tenants/',
    method: 'get',
    params
  })
}

// 租户详情（仅管理员）
export function getTenantDetail(tenantId: string) {
  return request({
    url: `/api/v1/tenants/${tenantId}`,
    method: 'get'
  })
}

// 创建租户（仅管理员）
export function createTenant(data: TenantCreate) {
  return request({
    url: '/api/v1/tenants/',
    method: 'post',
    data
  })
}

// 更新租户（仅管理员）
export function updateTenant(tenantId: string, data: TenantUpdate) {
  return request({
    url: `/api/v1/tenants/${tenantId}`,
    method: 'put',
    data
  })
}

// 删除租户（仅管理员）
export function deleteTenant(tenantId: string) {
  return request({
    url: `/api/v1/tenants/${tenantId}`,
    method: 'delete'
  })
}

// 租户使用情况（仅管理员）
export function getTenantUsage(tenantId: string) {
  return request({
    url: `/api/v1/tenants/${tenantId}/usage`,
    method: 'get'
  })
}
