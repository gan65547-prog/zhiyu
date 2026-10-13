export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

export interface LoginForm {
  email: string
  password: string
}

export interface RegisterForm {
  email: string
  password: string
  name: string
}

export interface AuthResponse {
  user: User
  access_token: string
  token_type: string
  expires_in: number
}

export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data: T
}
