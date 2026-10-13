import request from './request'
import type { SystemConfig } from '@/stores/userConfig'

export interface UserConfigPayload extends SystemConfig {
  embeddingModel: string
  llmModel: string
  temperature: number
  topK: number
  sessionTimeout: number
  twoFactorAuth: boolean
  ipWhitelist: string
}
const toApiPayload = (config: UserConfigPayload) => ({
  theme: config.theme,
  language: config.language,
  default_page: config.defaultPage,
  embedding_model: config.embeddingModel,
  llm_model: config.llmModel,
  temperature: config.temperature,
  top_k: config.topK,
  session_timeout_minutes: config.sessionTimeout,
  two_factor_auth_enabled: config.twoFactorAuth,
  ip_whitelist: config.ipWhitelist
})

const fromApiPayload = (payload: any): UserConfigPayload => ({
  theme: payload?.theme || 'light',
  language: payload?.language || 'zh-CN',
  defaultPage: payload?.default_page || '/',
  embeddingModel: payload?.embedding_model || 'bge-small-zh-v1.5',
  llmModel: payload?.llm_model || 'deepseek-chat',
  temperature: Number(payload?.temperature ?? 0.7),
  topK: Number(payload?.top_k ?? 5),
  sessionTimeout: Number(payload?.session_timeout_minutes ?? 1440),
  twoFactorAuth: Boolean(payload?.two_factor_auth_enabled),
  ipWhitelist: payload?.ip_whitelist || ''
})

export const userConfigApi = {
  async get(): Promise<UserConfigPayload> {
    const response = await request.get<any>('/api/v1/auth/me/config')
    return fromApiPayload(response?.data)
  },

  async update(config: UserConfigPayload): Promise<UserConfigPayload> {
    const response = await request.put<any>('/api/v1/auth/me/config', toApiPayload(config))
    return fromApiPayload(response?.data)
  }
}
