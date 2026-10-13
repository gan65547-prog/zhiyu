import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { workspaceApi } from '@/api/workspace'
import type { Workspace, WorkspaceCreate, WorkspaceUpdate, WorkspaceRole, WorkspaceMember } from '@/types/workspace'
import { useAuthStore } from './auth'

export const useWorkspaceStore = defineStore('workspace', () => {
  const workspaces = ref<Workspace[]>([])
  const currentWorkspace = ref<Workspace | null>(null)
  const currentMembership = ref<WorkspaceMember | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 检查用户是否已登录
  const isLoggedIn = computed(() => {
    const authStore = useAuthStore()
    return authStore.isLoggedIn
  })

  // 检查用户是否是超级管理员
  const isSuperuser = computed(() => {
    const authStore = useAuthStore()
    return authStore.isSuperuser
  })

  // 获取当前用户ID
  const currentUserId = computed(() => {
    const authStore = useAuthStore()
    return authStore.currentUser?.id || null
  })

  const hasWorkspaces = computed(() => workspaces.value.length > 0)
  const currentWorkspaceId = computed(() => currentWorkspace.value?.id || null)
  const currentWorkspaceName = computed(() => currentWorkspace.value?.name || '未选择工作空间')
  const currentRole = computed<WorkspaceRole | null>(() => currentMembership.value?.role || null)

  async function fetchWorkspaces(_params?: { page?: number; page_size?: number }) {
    // 超级管理员不获取工作空间列表（没有租户）
    if (isSuperuser.value) {
      workspaces.value = []
      return
    }
    
    // 如果用户未登录，直接返回空数组
    if (!isLoggedIn.value) {
      workspaces.value = []
      return
    }
    
    loading.value = true
    error.value = null
    try {
      const response = await workspaceApi.list()
      workspaces.value = response.items
    } catch (e: any) {
      error.value = e.message || '获取工作空间列表失败'
      // 不抛出错误，静默失败
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrentWorkspace() {
    // 超级管理员不获取当前工作空间
    if (isSuperuser.value) {
      currentWorkspace.value = null
      currentMembership.value = null
      return
    }

    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      currentWorkspace.value = null
      currentMembership.value = null
      return
    }

    try {
      currentWorkspace.value = await workspaceApi.getCurrent()

      // 将工作空间ID保存到localStorage
      if (currentWorkspace.value) {
        localStorage.setItem('currentWorkspaceId', currentWorkspace.value.id)
        console.log('WorkspaceStore: current workspace ID saved to localStorage:', currentWorkspace.value.id)
        // 获取当前用户的成员信息
        await fetchCurrentMembership(currentWorkspace.value.id)
      }
    } catch (e: any) {
      // 用户还没有工作空间，这是正常情况，不显示错误
      currentWorkspace.value = null
      currentMembership.value = null
      localStorage.removeItem('currentWorkspaceId')
    }
  }

  async function fetchCurrentMembership(workspaceId: string) {
    // 超级管理员不获取成员信息
    if (isSuperuser.value) {
      currentMembership.value = null
      return
    }
    
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      currentMembership.value = null
      return
    }
    
    // 每次重新拉取前先重置，避免沿用历史角色导致权限误判
    currentMembership.value = null

    try {
      console.log('Fetching membership for workspace:', workspaceId)
      const members = await workspaceApi.listMembers(workspaceId)
      console.log('Members received:', members)
      const userId = currentUserId.value
      console.log('Current user ID:', userId)
      
      if (userId) {
        currentMembership.value = members.find((m: any) => m.user_id === userId) || null
        console.log('Current membership:', currentMembership.value)
        console.log('Current role:', currentMembership.value?.role)
      }
    } catch (e: any) {
      currentMembership.value = null
      console.error('Failed to fetch current membership:', e)
    }
  }

  async function createWorkspace(data: WorkspaceCreate) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      error.value = '用户未登录'
      console.error('[WorkspaceStore] createWorkspace: user not logged in')
      throw new Error('用户未登录')
    }

    loading.value = true
    error.value = null
    console.log('[WorkspaceStore] createWorkspace: calling API with', data)
    try {
      const workspace = await workspaceApi.create(data)
      console.log('[WorkspaceStore] createWorkspace: API success', workspace)
      await fetchWorkspaces()
      if (workspace?.id) {
        currentWorkspace.value = workspace
        localStorage.setItem('currentWorkspaceId', workspace.id)
        await fetchCurrentMembership(workspace.id)
      } else {
        await fetchCurrentWorkspace()
      }
      return workspace
    } catch (e: any) {
      error.value = e.message || '创建工作空间失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateWorkspace(id: string, data: WorkspaceUpdate) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      error.value = '用户未登录'
      throw new Error('用户未登录')
    }
    
    loading.value = true
    error.value = null
    try {
      const workspace = await workspaceApi.update(id, data)
      const index = workspaces.value.findIndex(w => w.id === id)
      if (index !== -1) {
        workspaces.value[index] = workspace
      }
      if (currentWorkspace.value?.id === id) {
        currentWorkspace.value = workspace
      }
      return workspace
    } catch (e: any) {
      error.value = e.message || '更新工作空间失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteWorkspace(id: string) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      error.value = '用户未登录'
      throw new Error('用户未登录')
    }
    
    loading.value = true
    error.value = null
    try {
      await workspaceApi.delete(id)
      await fetchWorkspaces()
      await fetchCurrentWorkspace()
      if (currentWorkspace.value?.id) {
        localStorage.setItem('currentWorkspaceId', currentWorkspace.value.id)
      } else {
        localStorage.removeItem('currentWorkspaceId')
        currentMembership.value = null
      }
    } catch (e: any) {
      error.value = e.message || '删除工作空间失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function switchWorkspace(id: string) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      error.value = '用户未登录'
      throw new Error('用户未登录')
    }
    
    loading.value = true
    error.value = null
    try {
      const previousWorkspaceId =
        currentWorkspace.value?.id || localStorage.getItem('currentWorkspaceId')
      currentWorkspace.value = await workspaceApi.switch(id)
      if (currentWorkspace.value?.id) {
        localStorage.setItem('currentWorkspaceId', currentWorkspace.value.id)
      }
      
      // 获取当前用户的成员信息
      await fetchCurrentMembership(id)
      
      // 通知数据集存储重新加载数据
      const { useDatasetStore } = await import('./dataset')
      const datasetStore = useDatasetStore()
      const workspaceChanged = String(previousWorkspaceId || '') !== String(id || '')
      // 仅在“切换到不同工作空间”时清空当前知识库，避免刷新时把详情页清空。
      if (workspaceChanged) {
        datasetStore.setCurrentDataset(null)
        await datasetStore.fetchDatasets()
      } else {
        await datasetStore.fetchDatasets({ silent: true })
      }
      
      return currentWorkspace.value
    } catch (e: any) {
      error.value = e.message || '切换工作空间失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  function setCurrentWorkspace(workspace: Workspace) {
    currentWorkspace.value = workspace
  }

  return {
    workspaces,
    currentWorkspace,
    currentMembership,
    loading,
    error,
    hasWorkspaces,
    currentWorkspaceId,
    currentWorkspaceName,
    currentRole,
    fetchWorkspaces,
    fetchCurrentWorkspace,
    fetchCurrentMembership,
    createWorkspace,
    updateWorkspace,
    deleteWorkspace,
    switchWorkspace,
    setCurrentWorkspace,
    clearError
  }
})
