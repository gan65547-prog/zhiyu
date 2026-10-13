import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUserConfigStore } from '@/stores/userConfig'
import { useChatStore } from '@/stores/chat'
import { usePermission } from '@/composables/usePermission'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/HomeView.vue')
      },
      {
        path: 'workbench',
        name: 'Workbench',
        component: () => import('@/views/workbench/WorkbenchView.vue')
      },
      {
        path: 'tasks',
        name: 'TaskCenter',
        component: () => import('@/views/workbench/TaskCenterView.vue')
      },
      {
        path: 'assets',
        name: 'AssetCenter',
        component: () => import('@/views/workbench/AssetCenterView.vue')
      },
      {
        path: 'knowledge',
        name: 'KnowledgeHome',
        component: () => import('@/views/knowledge/KnowledgeHomeView.vue')
      },
      {
        path: 'knowledge/network',
        name: 'KnowledgeNetwork',
        component: () => import('@/views/knowledge/KnowledgeNetworkView.vue')
      },
      {
        path: 'research',
        name: 'ResearchHome',
        component: () => import('@/views/research/ResearchHomeView.vue')
      },
      {
        path: 'insights',
        name: 'LegacyInsights',
        redirect: { name: 'ResearchHome' }
      },
      {
        path: 'insights/:projectId',
        name: 'LegacyInsightDetail',
        redirect: { name: 'ResearchHome' }
      },
      {
        path: 'brainstorm',
        name: 'LegacyBrainstorm',
        redirect: { name: 'ContentHome' }
      },
      {
        path: 'hot-topics',
        name: 'LegacyHotTopics',
        redirect: { name: 'ResearchHome' }
      },
      {
        path: 'inspiration',
        name: 'LegacyInspiration',
        redirect: { name: 'KnowledgeHome' }
      },
      {
        path: 'bookshelf',
        name: 'LegacyBookshelf',
        redirect: { name: 'DatasetList' }
      },
      {
        path: 'agents',
        name: 'AgentHome',
        component: () => import('@/views/agents/AgentHomeView.vue')
      },
      {
        path: 'content',
        name: 'ContentHome',
        component: () => import('@/views/content/ContentHomeView.vue')
      },
      {
        path: 'data-center',
        name: 'DataCenter',
        component: () => import('@/views/data-center/DataCenterView.vue')
      },
      {
        path: 'platform-data',
        name: 'LegacyPlatformData',
        redirect: { name: 'ContentHome' }
      },
      {
        path: 'runs',
        name: 'RunArchive',
        component: () => import('@/views/workbench/RunArchiveView.vue')
      },
      {
        path: 'documents',
        redirect: { name: 'DatasetList' }
      },
      {
        path: 'documents/:documentId/read',
        name: 'DocumentReader',
        component: () => import('@/views/document/DocumentReaderView.vue'),
        meta: { title: '文档阅读台' }
      },
      {
        path: 'datasets',
        name: 'DatasetList',
        component: () => import('@/views/dataset/DatasetListView.vue')
      },
      {
        path: 'datasets/create',
        name: 'DatasetCreate',
        component: () => import('@/views/dataset/DatasetCreateView.vue')
      },
      {
        path: 'datasets/:id',
        name: 'DatasetDetail',
        component: () => import('@/views/dataset/DatasetDetailView.vue')
      },
      {
        path: 'datasets/:id/documents',
        redirect: (to) => ({ path: `/datasets/${to.params.id}` })
      },
      {
        path: 'datasets/:id/documents/upload',
        name: 'DocumentUpload',
        component: () => import('@/views/document/DocumentUploadView.vue')
      },
      {
        path: 'datasets/:id/documents/import-wechat',
        name: 'WechatImport',
        component: () => import('@/views/document/WechatImportView.vue')
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/chat/ChatView.vue')
      },
      {
        path: 'chat/:datasetId',
        name: 'ChatWithDataset',
        component: () => import('@/views/chat/ChatView.vue')
      },
      {
        path: 'workspaces',
        name: 'WorkspaceList',
        component: () => import('@/views/workspace/WorkspaceListView.vue')
      },
      {
        path: 'workspaces/:id/members',
        name: 'WorkspaceMembers',
        component: () => import('@/views/workspace/WorkspaceMemberView.vue')
      },
      // 用户管理路由（仅租户管理员）
      {
        path: 'users',
        name: 'UserList',
        component: () => import('@/views/UserListView.vue'),
        meta: { requiresTenantAdmin: true }
      },
      // 租户管理路由（仅管理员）
      {
        path: 'tenants',
        name: 'TenantList',
        component: () => import('@/views/tenant/TenantListView.vue'),
        meta: { requiresSuperuser: true }
      },
      {
        path: 'tenants/:id',
        name: 'TenantDetail',
        component: () => import('@/views/tenant/TenantDetailView.vue'),
        meta: { requiresSuperuser: true }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfileView.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue')
      },
      // 学习诊断
      {
        path: 'learning',
        name: 'LearningDiagnosis',
        component: () => import('@/views/learning/LearningDiagnosisView.vue')
      },
      {
        path: 'learning/report/:id',
        name: 'LearningReport',
        component: () => import('@/views/learning/LearningDiagnosisView.vue')
      },
      {
        path: 'learning/history',
        name: 'LearningHistory',
        component: () => import('@/views/learning/LearningDiagnosisView.vue')
      },
      {
        path: 'learning/practice/:id',
        name: 'LearningPractice',
        component: () => import('@/views/learning/LearningDiagnosisView.vue')
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  // 先在导航开始阶段立即中止问答流式请求，避免离开聊天页后仍占用连接
  if (from.path.startsWith('/chat') && !to.path.startsWith('/chat')) {
    const chatStore = useChatStore()
    chatStore.abortController?.abort()
    chatStore.resetTransientState()
  }

  const authStore = useAuthStore()
  const userConfigStore = useUserConfigStore()

  // 确保配置已加载
  if (!userConfigStore.isLoaded) {
    userConfigStore.loadConfig()
  }

  // 确保认证状态已初始化
  await authStore.initialize()

  // 需要登录
  if (!to.meta.public && !authStore.isLoggedIn) {
    next('/login')
    return
  }
  
  // 已登录访问登录/注册页 - 跳转到默认页面
  if ((to.name === 'Login' || to.name === 'Register') && authStore.isLoggedIn) {
    if (authStore.isSuperuser) {
      next('/tenants')
    } else {
      const defaultPage = userConfigStore.config.defaultPage
      const landingPage = defaultPage === '/datasets' ? '/' : (defaultPage || '/')
      next(landingPage)
    }
    return
  }

  // 已登录访问根路径 - 跳转到默认页面
  if (to.path === '/' && to.name === 'Home' && authStore.isLoggedIn) {
    if (authStore.isSuperuser) {
      next('/tenants')
    } else {
      const defaultPage = userConfigStore.config.defaultPage
      if (defaultPage && defaultPage !== '/' && defaultPage !== '/datasets') {
        next(defaultPage)
        return
      }
    }
  }
  
  // 需要管理员权限
  if (to.meta.requiresSuperuser && !authStore.isSuperuser) {
    next('/')
    return
  }
  
  // 需要租户管理员权限
  if (to.meta.requiresTenantAdmin && !authStore.isSuperuser) {
    // 检查用户是否有租户管理员权限（至少是一个工作空间的OWNER或ADMIN）
    const { canManageWorkspace } = usePermission()
    if (!canManageWorkspace.value) {
      next('/')
      return
    }
  }
  
  next()
})

export default router
