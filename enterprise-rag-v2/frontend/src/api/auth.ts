import request from './request'
import type { LoginForm, RegisterForm, AuthResponse, ApiResponse } from '@/types'
import type { User } from '@/types/user'

export const login = (data: LoginForm) => {
  return request.post<any, ApiResponse<AuthResponse>>('/api/v1/auth/login', data)
}

export const register = (data: RegisterForm) => {
  return request.post<any, ApiResponse<AuthResponse>>('/api/v1/auth/register', data)
}

export const refreshToken = () => {
  return request.post<any, ApiResponse<{ access_token: string; expires_in: number }>>('/api/v1/auth/refresh', {})
}

export const getCurrentUser = () => {
  return request.get<any, ApiResponse<User>>('/api/v1/auth/me', {
    skipAuthErrorHandler: true
  } as any)
}

export const switchTenantContext = (tenant_id: string) => {
  return request.post<any, ApiResponse<{ tenant_id: string; tenant_name: string }>>(
    '/api/v1/auth/me/tenant-context',
    { tenant_id },
  )
}
