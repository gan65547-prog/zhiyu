<template>
  <div
    class="app-header"
    :class="{ 'is-switching': workspaceStore.loading }"
  >
    <div class="header-left">
      <button
        class="mobile-menu-button"
        type="button"
        aria-label="打开导航菜单"
        @click="$emit('toggle-sidebar')"
      >
        <el-icon><Menu /></el-icon>
      </button>
      <div
        v-if="!authStore.isSuperuser"
        class="workspace-switcher"
      >
        <el-dropdown
          trigger="click"
          :teleported="true"
          popper-class="workspace-dropdown-popper"
          @command="handleWorkspaceSwitch"
        >
          <span class="workspace-trigger">
            <el-icon><OfficeBuilding /></el-icon>
            <span class="workspace-name">{{ currentWorkspace?.name || '选择工作空间' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="ws in workspaceStore.workspaces"
                :key="ws.id"
                :command="ws.id"
                :disabled="ws.id === currentWorkspace?.id"
              >
                <el-icon v-if="ws.id === currentWorkspace?.id">
                  <Check />
                </el-icon>
                {{ ws.name }}
              </el-dropdown-item>
              <el-dropdown-item
                v-if="canCreateWorkspace"
                divided
                command="create"
              >
                <el-icon><Plus /></el-icon>
                创建工作空间
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <h2 class="page-title">
        {{ title }}
      </h2>
    </div>
    <div class="header-right">
      <div class="global-search">
        <el-input
          v-model="searchQuery"
          clearable
          placeholder="搜索素材、知识、研究"
          @keyup.enter="runSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <div
        class="theme-toggle"
        :title="themeTooltip"
        @click="toggleTheme"
      >
        <el-icon :size="18">
          <Sunny v-if="userConfigStore?.effectiveTheme === 'dark'" />
          <Moon v-else-if="userConfigStore?.effectiveTheme === 'light'" />
          <Monitor v-else />
        </el-icon>
      </div>

      <el-dropdown
        :teleported="true"
        popper-class="header-user-dropdown-popper"
        @command="handleCommand"
      >
        <span class="user-info">
          <el-avatar
            :size="32"
            src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png"
          />
          <span class="username">{{ authStore.currentUser?.name || '用户' }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              个人中心
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              设置
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="logout"
            >
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <el-dialog
      v-model="searchDialogVisible"
      title="工作台搜索"
      width="620px"
      destroy-on-close
    >
      <el-input
        v-model="searchQuery"
        autofocus
        clearable
        placeholder="输入关键词并回车"
        @keyup.enter="runSearch"
      />
      <div
        v-loading="searchLoading"
        class="search-results"
      >
        <button
          v-for="item in searchItems"
          :key="`${item.kind}-${item.id}`"
          class="search-result"
          @click="openSearchResult(item.route)"
        >
          <strong>{{ item.title }}</strong>
          <span>{{ kindLabel(item.kind) }} · {{ item.snippet || '暂无摘要' }}</span>
        </button>
        <el-empty
          v-if="!searchLoading && !searchItems.length"
          description="没有匹配结果"
          :image-size="70"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { usePermission } from '@/composables/usePermission'
import { ElMessageBox, ElMessage } from 'element-plus'
import { ArrowDown, OfficeBuilding, Check, Plus, Search, Sunny, Moon, Monitor, Menu } from '@element-plus/icons-vue'
import { useUserConfigStore } from '@/stores/userConfig'
import { shouldSkipDuplicateErrorToast } from '@/api/request'
import { workbenchApi, type WorkbenchSearchItem } from '@/api/workbench'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const userConfigStore = useUserConfigStore()
const { canCreateWorkspace } = usePermission()

defineEmits<{ (event: 'toggle-sidebar'): void }>()

const openCreateWorkspaceDialog = inject<() => void>('openCreateWorkspaceDialog', () => {
  console.error('[AppHeader] openCreateWorkspaceDialog not provided by parent')
})

const title = computed(() => {
  return (route.meta.title as string) || '知域引擎'
})

const themeTooltip = computed(() => {
  const theme = userConfigStore?.config?.theme || 'light'
  if (theme === 'light') return '切换到深色模式 (当前: 浅色)'
  if (theme === 'dark') return '切换到跟随系统 (当前: 深色)'
  return '切换到浅色模式 (当前: 跟随系统)'
})

const toggleTheme = () => {
  userConfigStore?.toggleTheme()
}

const currentWorkspace = computed(() => workspaceStore.currentWorkspace)
const searchQuery = ref('')
const searchDialogVisible = ref(false)
const searchLoading = ref(false)
const searchItems = ref<WorkbenchSearchItem[]>([])

async function runSearch() {
  const query = searchQuery.value.trim()
  if (!query) return
  if (!workspaceStore.currentWorkspaceId) {
    ElMessage.warning('请先选择工作空间')
    return
  }
  searchDialogVisible.value = true
  searchLoading.value = true
  try {
    searchItems.value = (await workbenchApi.search(workspaceStore.currentWorkspaceId, query)).items || []
  } catch (error: any) {
    searchItems.value = []
    ElMessage.error(error?.response?.data?.detail || '搜索失败，请稍后重试')
  } finally {
    searchLoading.value = false
  }
}

function openSearchResult(routePath: string) {
  searchDialogVisible.value = false
  router.push(routePath)
}

function kindLabel(kind: string) {
  return ({ asset: '素材', dataset: '知识库', document: '文档', knowledge: '知识卡片', research: '研究项目', content_topic: '内容选题', content_draft: '内容草稿' }[kind] || kind)
}

onMounted(async () => {
  userConfigStore.init()

  if (authStore.isSuperuser) {
    return
  }

  try {
    await workspaceStore.fetchWorkspaces()
  } catch (e) {
    console.error('Failed to fetch workspaces:', e)
  }

  const savedWorkspaceId = localStorage.getItem('currentWorkspaceId')
  if (savedWorkspaceId && workspaceStore.workspaces.length > 0) {
    const savedWorkspace = workspaceStore.workspaces.find(ws => ws.id === savedWorkspaceId)
    if (savedWorkspace) {
      try {
        await workspaceStore.switchWorkspace(savedWorkspaceId)
        workspaceStore.setCurrentWorkspace(savedWorkspace)
      } catch (e) {
        console.error('Failed to restore workspace:', e)
        localStorage.removeItem('currentWorkspaceId')
        if (workspaceStore.workspaces.length > 0) {
          workspaceStore.setCurrentWorkspace(workspaceStore.workspaces[0])
          localStorage.setItem('currentWorkspaceId', workspaceStore.workspaces[0].id)
        }
      }
    } else {
      localStorage.removeItem('currentWorkspaceId')
      if (workspaceStore.workspaces.length > 0) {
        workspaceStore.setCurrentWorkspace(workspaceStore.workspaces[0])
        localStorage.setItem('currentWorkspaceId', workspaceStore.workspaces[0].id)
      }
    }
  } else {
    try {
      await workspaceStore.fetchCurrentWorkspace()
      if (workspaceStore.currentWorkspace) {
        localStorage.setItem('currentWorkspaceId', workspaceStore.currentWorkspace.id)
      }
    } catch (e) {
      console.error('Failed to fetch current workspace:', e)
    }
    if (workspaceStore.workspaces.length > 0 && !workspaceStore.currentWorkspace) {
      workspaceStore.setCurrentWorkspace(workspaceStore.workspaces[0])
      localStorage.setItem('currentWorkspaceId', workspaceStore.workspaces[0].id)
    }
  }
})

const handleWorkspaceSwitch = async (command: string) => {
  if (command === 'create') {
    openCreateWorkspaceDialog()
    return
  }

  const workspace = workspaceStore.workspaces.find(ws => ws.id === command)
  if (workspace) {
    try {
      await workspaceStore.switchWorkspace(workspace.id)
      workspaceStore.setCurrentWorkspace(workspace)
      localStorage.setItem('currentWorkspaceId', workspace.id)

      ElMessage.success(`已切换到工作空间: ${workspace.name}`)
    } catch (e: any) {
      if (!shouldSkipDuplicateErrorToast(e)) {
        ElMessage.error(e.message || '切换失败')
      }
    }
  }
}

const handleCommand = async (command: string) => {
  if (command === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', {
      type: 'warning'
    })
    await authStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'settings') {
    router.push('/settings')
  }
}
</script>

<style scoped lang="scss">
.app-header {
  height: var(--header-height, 72px);
  padding: 0 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.64);
  border-bottom: 1px solid rgba(62, 42, 108, 0.07);
  transition: background-color 0.3s, border-color 0.3s;

  &.is-switching {
    background: rgba(255, 255, 255, 0.96);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 24px;

    .workspace-switcher {
      .workspace-trigger {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 9px 13px;
        border-radius: 12px;
        cursor: pointer;
        border: 1px solid rgba(116, 65, 232, 0.15);
        background: rgba(250, 248, 255, 0.82);
        transition: all 0.2s ease;

        &:hover {
          background-color: #f6f1ff;
          border-color: rgba(116, 65, 232, 0.32);
        }

        .workspace-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--el-text-color-primary);
        }
      }
    }

    .page-title {
      margin: 0;
      min-width: 0;
      overflow: hidden;
      font-size: 20px;
      font-weight: 700;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--el-text-color-primary);
    }
  }

  .mobile-menu-button {
    display: none;
  }

  .global-search {
    width: min(360px, 32vw);
    margin-right: 8px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;

    .theme-toggle {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--el-text-color-secondary);
      transition: all 0.3s ease;
      border: 1px solid rgba(116, 65, 232, 0.14);
      background: rgba(255, 255, 255, 0.72);

      &:hover {
        background-color: #f6f1ff;
        color: var(--el-text-color-primary);
        border-color: rgba(124, 77, 200, 0.34);
      }

      &:active {
        transform: scale(0.95);
      }

      .el-icon {
        transition: transform 0.3s ease;
      }

      &:hover .el-icon {
        transform: rotate(15deg);
      }
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 10px;
      border-radius: 999px;
      transition: background-color 0.2s ease;

      &:hover {
        background: #f6f1ff;
      }

      .username {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }
    }
  }
}

:global(html.dark) .app-header {
  background: rgba(17, 24, 39, 0.92);
  border-bottom-color: rgba(148, 163, 184, 0.18);
}

:global(html.dark) .app-header.is-switching {
  background: rgba(17, 24, 39, 0.94);
}

:global(html.dark) .app-header .header-left .workspace-switcher .workspace-trigger {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(30, 41, 59, 0.72);
}

:global(html.dark) .app-header .header-right .theme-toggle {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(30, 41, 59, 0.7);
}

@media (max-width: 900px) {
  .app-header {
    padding: 0 20px;

    .header-left {
      min-width: 0;
      gap: 12px;
    }

    .page-title {
      max-width: 120px;
    }

    .global-search {
      width: min(260px, 28vw);
    }
  }
}

@media (max-width: 768px) {
  .app-header {
    height: 64px;
    padding: 0 14px;

    .header-left {
      gap: 10px;
      min-width: 0;
    }

    .mobile-menu-button {
      display: inline-grid;
      width: 36px;
      height: 36px;
      flex: 0 0 36px;
      place-items: center;
      padding: 0;
      color: var(--el-text-color-primary);
      cursor: pointer;
      border: 1px solid rgba(116, 65, 232, 0.14);
      border-radius: 11px;
      background: rgba(255, 255, 255, 0.78);
    }

    .workspace-switcher {
      max-width: 150px;
      overflow: hidden;
    }

    .workspace-name {
      max-width: 98px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .header-right {
      gap: 6px;
    }

    .global-search {
      display: none;
    }

    .username,
    .user-info > .el-icon {
      display: none;
    }

    .user-info {
      padding: 2px;
    }
  }
}

@media (max-width: 1360px) {
  .app-header .header-left .page-title {
    display: none;
  }
}
</style>

<style lang="scss">
.workspace-dropdown-popper,
.header-user-dropdown-popper {
  z-index: 100000 !important;
}

.workspace-dropdown-popper {
  .el-dropdown-menu {
    min-width: 188px;
  }
}

.search-results {
  min-height: 120px;
  margin-top: 16px;
}

.search-result {
  display: block;
  width: 100%;
  padding: 12px;
  color: var(--el-text-color-primary);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.search-result:hover {
  background: var(--el-fill-color-light);
}

.search-result strong,
.search-result span {
  display: block;
}

.search-result span {
  margin-top: 5px;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
