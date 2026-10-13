import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getCurrentUser as getCurrentUserApi, switchTenantContext as switchTenantContextApi } from '@/api/auth'
import type { LoginForm, RegisterForm } from '@/types'
import { resetAuthErrorState } from '@/api/request'

export const useAuthStore = defineStore('auth', () => {
  const AUTH_USER_KEY = 'ganfy_auth_user'
  const CHAT_DATASET_KEY = 'enterprise-rag-chat:lastDatasetId'
  const CHAT_CONVERSATION_KEY = 'enterprise-rag-chat:lastConversationId'
  const CHAT_REVISIT_KEY = 'enterprise-rag-chat:revisitNext'

  const user = ref<any | null>(null)
  const token = ref<string>('')
  const loading = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const currentUser = computed(() => user.value)
  const isSuperuser = computed(() => user.value?.is_superuser === true)
  const isTenantAdmin = computed(() => user.value?.is_tenant_admin === true)
  const tenantId = computed(() => user.value?.tenant_id || null)

  function persistAuthState() {
    if (user.value) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user.value))
    } else {
      localStorage.removeItem(AUTH_USER_KEY)
    }
  }

  function clearChatNavigationState() {
    // 问答上下文不能跨账号复用，否则新账号会带入旧租户的 dataset/conversation ID。
    try {
      sessionStorage.removeItem(CHAT_DATASET_KEY)
      sessionStorage.removeItem(CHAT_CONVERSATION_KEY)
      sessionStorage.removeItem(CHAT_REVISIT_KEY)
    } catch {
      /* ignore storage access failures */
    }
  }

  // 清理旧版 localStorage token（迁移到 httpOnly cookie）
  localStorage.removeItem('ganfy_auth_token')

  function restoreAuthState() {
    const cachedUser = localStorage.getItem(AUTH_USER_KEY)

    if (cachedUser) {
      try {
        user.value = JSON.parse(cachedUser)
      } catch {
        user.value = null
        localStorage.removeItem(AUTH_USER_KEY)
      }
    }
  }

  async function loginUser(form: LoginForm) {
    loading.value = true
    try {
      const res = await loginApi(form)
      
      // 确保res.data存在且有access_token
      if (res && res.data && res.data.access_token) {
        token.value = res.data.access_token || 'cookie-session'
        user.value = res.data.user
        persistAuthState()
        clearChatNavigationState()
        resetAuthErrorState()

        const { useChatStore } = await import('./chat')
        useChatStore().resetAllState()
        
        // 认证成功不能被工作空间接口的瞬时失败阻断。
        // 工作空间数据会在 MainLayout / 页面挂载后继续重试加载。
        try {
          const { useWorkspaceStore } = await import('./workspace')
          const workspaceStore = useWorkspaceStore()
          await workspaceStore.fetchCurrentWorkspace()
          await workspaceStore.fetchWorkspaces()
        } catch (workspaceError) {
          console.warn('[Auth] 登录成功，但工作空间暂时加载失败，将在页面侧重试', workspaceError)
        }
        
        return res
      } else {
        throw new Error('Invalid login response')
      }
    } catch (error) {
      throw error
    } finally {
      loading.value = false
    }
  }

  async function registerUser(form: RegisterForm) {
    loading.value = true
    try {
      const res = await registerApi(form)
      token.value = res.data.access_token || 'cookie-session'
      user.value = res.data.user
      persistAuthState()
      clearChatNavigationState()

      const { useChatStore } = await import('./chat')
      useChatStore().resetAllState()
      
      // 注册成功不能被自动创建的工作空间加载失败阻断。
      try {
        const { useWorkspaceStore } = await import('./workspace')
        const workspaceStore = useWorkspaceStore()
        await workspaceStore.fetchCurrentWorkspace()
      } catch (workspaceError) {
        console.warn('[Auth] 注册成功，但工作空间暂时加载失败，将在页面侧重试', workspaceError)
      }
      
      return res
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrentUser() {
    const prevId = user.value?.id
    const prevTenantId = user.value?.tenant_id
    try {
      const res = await getCurrentUserApi()
      user.value = res.data
      if (user.value && !token.value) {
        token.value = 'cookie-session'
      }
      persistAuthState()
      if (
        user.value &&
        (prevId !== user.value.id || prevTenantId !== user.value.tenant_id)
      ) {
        const { useChatStore } = await import('./chat')
        useChatStore().resetAllState()
      }
    } catch (e: any) {
      // 只有明确的 401 才代表会话失效；500、网络错误或后端依赖暂时不可用时
      // 保留本地会话，让用户可以继续查看页面并在后续请求中恢复数据。
      if (e?.response?.status === 401) {
        user.value = null
        token.value = ''
        persistAuthState()
      } else if (!user.value) {
        console.error('Failed to fetch current user:', e)
        restoreAuthState()
        if (user.value && !token.value) token.value = 'cookie-session'
      }
      const { useChatStore } = await import('./chat')
      if (!token.value) useChatStore().resetAllState()
    }
  }

  async function logout() {
    user.value = null
    token.value = ''
    persistAuthState()
    clearChatNavigationState()

    const { useChatStore } = await import('./chat')
    useChatStore().resetAllState()
    
    // 清理工作空间状态
    const { useWorkspaceStore } = await import('./workspace')
    const workspaceStore = useWorkspaceStore()
    workspaceStore.workspaces = []
    workspaceStore.currentWorkspace = null
    workspaceStore.currentMembership = null
  }

  async function switchTenantContext(tenantId: string) {
    if (!isSuperuser.value) throw new Error('仅超级管理员可以切换租户上下文')
    await switchTenantContextApi(tenantId)
    const { useChatStore } = await import('./chat')
    useChatStore().resetAllState()
    const { useDatasetStore } = await import('./dataset')
    const datasetStore = useDatasetStore()
    datasetStore.datasets = []
    const { useWorkspaceStore } = await import('./workspace')
    const workspaceStore = useWorkspaceStore()
    workspaceStore.workspaces = []
    workspaceStore.currentWorkspace = null
    workspaceStore.currentMembership = null
    await fetchCurrentUser()
    await workspaceStore.fetchCurrentWorkspace()
    await workspaceStore.fetchWorkspaces()
    await datasetStore.fetchDatasets()
  }

  // 初始化认证状态
  async function initialize() {
    if (initialized.value) {
      return
    }

    restoreAuthState()
    const prevUserId = user.value?.id
    const prevTenantId = user.value?.tenant_id

    // 有缓存的用户信息或有 httpOnly cookie 时，拉取最新用户信息验证会话有效性
    if (user.value) {
      token.value = 'cookie-session'
    }
    try {
      await fetchCurrentUser()
    } catch (e) {
      console.error('Failed to fetch current user:', e)
      token.value = ''
      user.value = null
      persistAuthState()
    }

    const { useChatStore } = await import('./chat')
    const chatStore = useChatStore()
    if (!token.value || !user.value) {
      chatStore.resetAllState()
    } else if (
      prevUserId !== user.value?.id ||
      prevTenantId !== user.value?.tenant_id
    ) {
      chatStore.resetAllState()
    }

    // 如果已登录，获取当前工作空间和工作空间列表
    if (token.value) {
      try {
        const { useWorkspaceStore } = await import('./workspace')
        const workspaceStore = useWorkspaceStore()
        await workspaceStore.fetchCurrentWorkspace()
        await workspaceStore.fetchWorkspaces()
      } catch (e) {
        console.error('Failed to fetch workspace data:', e)
      }
    }
    
    initialized.value = true
  }

  return {
    user,
    token,
    loading,
    initialized,
    isLoggedIn,
    currentUser,
    isSuperuser,
    isTenantAdmin,
    tenantId,
    loginUser,
    registerUser,
    fetchCurrentUser,
    logout,
    switchTenantContext,
    initialize
  }
})
