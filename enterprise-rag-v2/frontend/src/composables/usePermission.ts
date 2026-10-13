/**
 * 权限检查 Composable
 * 
 * 提供按钮级别的权限控制功能
 */

import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import type { WorkspaceRole } from '@/types/workspace'

export function usePermission() {
  const authStore = useAuthStore()
  const workspaceStore = useWorkspaceStore()

  // 检查是否为超级管理员
  const isSuperAdmin = computed(() => authStore.isSuperuser)
  const isTenantAdmin = computed(() => authStore.isTenantAdmin)
  const isLoggedIn = computed(() => authStore.isLoggedIn)

  // 获取当前工作空间中的角色（从 workspaceStore 获取）
  const currentRole = computed<WorkspaceRole | null>(() => {
    return workspaceStore.currentRole
  })

  // 检查角色层级权限
  const hasRole = (requiredRole: WorkspaceRole): boolean => {
    // 超级管理员直接通过
    if (isSuperAdmin.value) return true

    // 如果没有角色，返回 false
    if (!currentRole.value) return false

    // 角色层级：OWNER > ADMIN > MEMBER > VIEWER
    const roleHierarchy: Record<WorkspaceRole, number> = {
      owner: 4,
      admin: 3,
      member: 2,
      viewer: 1
    }

    return roleHierarchy[currentRole.value] >= roleHierarchy[requiredRole]
  }

  // 检查是否可以创建知识库
  const canCreateDataset = computed(() => {
    return isSuperAdmin.value || hasRole('member')
  })

  // 检查是否可以编辑知识库
  const canEditDataset = computed(() => {
    return isSuperAdmin.value || hasRole('member')
  })

  // 检查是否可以删除知识库
  const canDeleteDataset = computed(() => {
    return isSuperAdmin.value || hasRole('member')
  })

  // 检查是否可以上传文档
  const canUploadDocument = computed(() => {
    return isSuperAdmin.value || hasRole('member')
  })

  // 检查是否可以删除文档
  const canDeleteDocument = computed(() => {
    return isSuperAdmin.value || hasRole('member')
  })

  // 检查是否可以管理工作空间
  const canManageWorkspace = computed(() => {
    // 兼容后端 is_tenant_admin 字段偶发未回传的情况：
    // 只要当前工作空间角色达到 admin，也允许进入管理页面。
    return isSuperAdmin.value || isTenantAdmin.value || hasRole('admin')
  })

  // 检查是否可以创建工作空间（避免“无工作空间时无法自救”）
  const canCreateWorkspace = computed(() => {
    if (isSuperAdmin.value) return false
    return isLoggedIn.value
  })

  // 检查是否可以删除工作空间
  const canDeleteWorkspace = computed(() => {
    return isSuperAdmin.value || hasRole('owner')
  })

  // 检查是否可以管理成员
  const canManageMembers = computed(() => {
    return isSuperAdmin.value || isTenantAdmin.value || hasRole('admin')
  })

  return {
    isSuperAdmin,
    isTenantAdmin,
    currentRole,
    hasRole,
    canCreateDataset,
    canEditDataset,
    canDeleteDataset,
    canUploadDocument,
    canDeleteDocument,
    canCreateWorkspace,
    canManageWorkspace,
    canDeleteWorkspace,
    canManageMembers
  }
}
