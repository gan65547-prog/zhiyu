import axios, { AxiosInstance, AxiosError } from 'axios'

type RequestConfigFlags = {
  skipGlobalErrorHandler?: boolean
  skipAuthErrorHandler?: boolean
  _authRetry?: boolean
}

/**
 * 与下方 response 拦截器已弹 Toast 的 HTTP 分支一致。
 * 业务代码在 catch 里若返回 true，则不要再 ElMessage / Toast，避免与全局提示重复
 * （例如 403 配额已由拦截器展示业务文案，不应再显示「Request failed with status code 403」）。
 */
export function shouldSkipDuplicateErrorToast(error: unknown): boolean {
  const err = error as AxiosError
  const cfg = err.config as RequestConfigFlags | undefined
  if (cfg?.skipGlobalErrorHandler) {
    return false
  }

  if (err.code === 'ECONNABORTED' || (err.message || '').toLowerCase().includes('timeout')) {
    return true
  }

  const status = err.response?.status
  if (status == null) {
    return false
  }
  if (status === 401) return true
  if (status >= 500) return true
  if (status === 409 || status === 403 || status === 404 || status === 400 || status === 429) return true
  return false
}
import { ElMessage } from 'element-plus'
import router from '@/router'

const request: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 60000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

let isShowingAuthError = false

/** 同一接口短时间内重复 500 时只提示一次，避免轮询/重渲染刷爆 Toast */
let lastServerErrorToast = { path: '', time: 0 }
const SERVER_ERROR_TOAST_INTERVAL_MS = 4000
let lastRateLimitToast = { path: '', time: 0 }
const RATE_LIMIT_TOAST_INTERVAL_MS = 4000

// 导入认证状态管理
import { useAuthStore } from '@/stores/auth'

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

let refreshPromise: Promise<string | null> | null = null

/**
 * 通过 httpOnly refresh cookie 更新 access cookie，同时把新的短期 token
 * 写回 Pinia。所有并发的 401 请求共享同一个 Promise，避免同时刷新导致
 * refresh token 轮换冲突。
 */
async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise

  refreshPromise = axios
    .post('/api/v1/auth/refresh', {}, {
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
        ...(getCookie('csrf_token') ? { 'X-CSRF-Token': getCookie('csrf_token') } : {})
      }
    })
    .then((response) => {
      const accessToken = response.data?.data?.access_token
      if (!accessToken) return null
      const authStore = useAuthStore()
      authStore.token = accessToken
      resetAuthErrorState()
      return accessToken as string
    })
    .catch(() => null)
    .finally(() => {
      refreshPromise = null
    })

  return refreshPromise
}

request.interceptors.request.use(
  (config) => {
    // 对非 GET 请求自动附加 CSRF Token（Double Submit Cookie 模式）
    if (config.method && !['get', 'head', 'options'].includes(config.method)) {
      const csrfToken = getCookie('csrf_token')
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }

    // 跳过登录和注册请求的Authorization头
    const loginPaths = ['/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/refresh']
    // 提取路径部分，不管是相对路径还是完整URL
    const urlPath = config.url?.split('?')[0]?.split('#')[0] || ''
    const normalizedPath = urlPath.startsWith('/') ? urlPath : `/${urlPath}`
    if (!loginPaths.some(path => normalizedPath.includes(path))) {
      // 从认证状态管理中获取token，而不是直接从localStorage中获取
      try {
        const authStore = useAuthStore()
        const token = authStore.token
        if (token && token !== 'cookie-session') {
          config.headers.Authorization = `Bearer ${token}`
        }
      } catch (e) {
        // ignore
      }
      // 不再直接拒绝请求，而是允许请求继续，让后端返回401错误
      // 这样可以让前端的错误处理逻辑更统一
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    return response.data
  },
  async (error: AxiosError) => {
    const { response, code } = error
    const originalConfig = error.config as (RequestConfigFlags & { url?: string; method?: string }) | undefined
    const skipGlobalErrorHandler = Boolean(originalConfig?.skipGlobalErrorHandler)
    const skipAuthErrorHandler = Boolean(originalConfig?.skipAuthErrorHandler)

    if (skipGlobalErrorHandler) {
      return Promise.reject(error)
    }

    // 处理超时错误
    if (code === 'ECONNABORTED' || error.message.includes('timeout')) {
      ElMessage.error('请求超时，请检查网络连接后重试')
      return Promise.reject(error)
    }

    // 跳过登录请求的 401 错误处理，因为登录失败本身就是 401
    const urlPath = error.config?.url?.split('?')[0]?.split('#')[0] || ''
    const normalizedPath = urlPath.startsWith('/') ? urlPath : `/${urlPath}`

    // 访问令牌短时过期时，先用 refresh cookie 更新令牌并重放原请求。
    // 登录、刷新本身以及显式跳过认证处理的请求不进入该分支。
    if (
      response?.status === 401 &&
      !normalizedPath.includes('/auth/login') &&
      !normalizedPath.includes('/auth/refresh') &&
      !skipAuthErrorHandler &&
      !originalConfig?._authRetry &&
      error.config
    ) {
      const nextConfig = error.config as typeof error.config & RequestConfigFlags
      nextConfig._authRetry = true
      const accessToken = await refreshAccessToken()
      if (accessToken) {
        return request(nextConfig)
      }
    }

    if (
      response?.status === 401 &&
      !normalizedPath.includes('/auth/login') &&
      !skipAuthErrorHandler
    ) {
      if (!isShowingAuthError) {
        isShowingAuthError = true
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
      }
    } else if (response && response.status === 503) {
      const detail = (response.data as { detail?: unknown })?.detail
      const errorMessage = detail && typeof detail === 'object'
        ? String((detail as Record<string, unknown>).message || '当前外部服务尚未配置')
        : typeof detail === 'string' ? detail : '当前外部服务尚未配置'
      ElMessage.warning(errorMessage)
    } else if (response && response.status >= 500) {
      const now = Date.now()
      if (
        normalizedPath !== lastServerErrorToast.path ||
        now - lastServerErrorToast.time > SERVER_ERROR_TOAST_INTERVAL_MS
      ) {
        lastServerErrorToast = { path: normalizedPath, time: now }
        ElMessage.error('服务器内部错误，请稍后重试')
      }
    } else if (response && response.status === 409) {
      // 处理409冲突错误（如用户名或邮箱已存在）
      const errorData = response.data as { detail?: unknown }
      const errorMessage = typeof errorData?.detail === 'string' ? errorData.detail : '操作冲突，请检查输入信息'
      ElMessage.error(errorMessage)
    } else if (response && response.status === 403) {
      // 处理403错误（权限不足 / 配额超限）
      const detail = (response.data as { detail?: unknown })?.detail
      if (detail && typeof detail === 'object' && (detail as Record<string, unknown>).error === 'QUOTA_EXCEEDED') {
        const detailData = detail as Record<string, unknown>
        const quotaMessage = [detailData.message, detailData.upgrade_hint].filter(Boolean).join('，')
        ElMessage.error(quotaMessage || '当前部署资源上限已达到，请联系管理员调整')
      } else {
        const errorMessage = typeof detail === 'string' ? detail : '您没有权限执行此操作'
        ElMessage.error(errorMessage)
      }
    } else if (response && response.status === 404) {
      // 处理404错误
      ElMessage.error('请求的资源不存在')
    } else if (response && response.status === 400) {
      // 处理400错误
      const errorData = response.data as { detail?: unknown }
      const errorMessage = typeof errorData?.detail === 'string' ? errorData.detail : '请求参数错误，请检查输入信息'
      ElMessage.error(errorMessage)
    } else if (response && response.status === 429) {
      const now = Date.now()
      if (normalizedPath !== lastRateLimitToast.path || now - lastRateLimitToast.time > RATE_LIMIT_TOAST_INTERVAL_MS) {
        lastRateLimitToast = { path: normalizedPath, time: now }
        ElMessage.warning('请求较频繁，系统正在保护服务，请稍后再试')
      }
    }

    return Promise.reject(error)
  }
)

// 拦截器在运行时返回 response.data，AxiosInstance 的声明无法表达这一变更。
// 在统一 API 类型改造完成前，将导出边界收敛为 unknown-facing client，避免调用方误把已解包数据当 AxiosResponse。
type RequestClient = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'patch' | 'delete'> & {
  (config: any): Promise<any>
  get<_T = unknown, R = any>(url: string, config?: any): Promise<R>
  post<_T = unknown, R = any>(url: string, data?: any, config?: any): Promise<R>
  put<_T = unknown, R = any>(url: string, data?: any, config?: any): Promise<R>
  patch<_T = unknown, R = any>(url: string, data?: any, config?: any): Promise<R>
  delete<_T = unknown, R = any>(url: string, config?: any): Promise<R>
}

export default request as unknown as RequestClient

export function resetAuthErrorState() {
  isShowingAuthError = false
}
