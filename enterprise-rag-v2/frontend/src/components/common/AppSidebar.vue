<template>
  <div
    class="sidebar-container"
    :class="{ 'is-mobile-open': mobileOpen }"
  >
    <!-- 租户切换器（仅管理员） -->
    <TenantSwitcher v-if="authStore.isSuperuser" />
    
    <el-menu
      :default-active="activeMenu"
      class="sidebar-menu"
      :router="true"
      @select="handleSelect"
    >
      <div class="logo">
        <el-icon :size="24">
          <Collection />
        </el-icon>
        <span>知域引擎</span>
      </div>

      <!-- 普通用户菜单 -->
      <template v-if="!authStore.isSuperuser">
        <div class="menu-section-label">总览</div>
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/workbench">
          <el-icon><Cpu /></el-icon>
          <span>工作台</span>
        </el-menu-item>

        <div class="menu-section-label">知识沉淀</div>
        <el-menu-item index="/assets">
          <el-icon><Collection /></el-icon>
          <span>资料</span>
        </el-menu-item>

        <el-menu-item index="/knowledge">
          <el-icon><Reading /></el-icon>
          <span>知识</span>
        </el-menu-item>

        <el-menu-item index="/knowledge/network">
          <el-icon><DataAnalysis /></el-icon>
          <span>知识星图</span>
        </el-menu-item>

        <div class="menu-section-label">研究与生产</div>
        <el-menu-item index="/research">
          <el-icon><Compass /></el-icon>
          <span>研究洞察</span>
        </el-menu-item>

        <div class="menu-section-label">生产与反馈</div>
        <el-menu-item index="/content">
          <el-icon><EditPen /></el-icon>
          <span>内容中心</span>
        </el-menu-item>

        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>任务中心</span>
        </el-menu-item>

        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>

        <div class="menu-section-label">管理</div>
        <el-menu-item
          v-if="canManageWorkspace || canCreateWorkspace"
          index="/workspaces"
        >
          <el-icon><Setting /></el-icon>
          <span>工作空间</span>
        </el-menu-item>

        <!-- 用户管理（仅管理员） -->
        <el-menu-item
          v-if="canManageMembers"
          index="/users"
        >
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-divider class="sidebar-divider" />

        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Tools /></el-icon>
          <span>系统设置</span>
        </el-menu-item>

      </template>

      <!-- 超级管理员菜单 -->
      <template v-else>
        <el-menu-item index="/tenants">
          <el-icon><OfficeBuilding /></el-icon>
          <span>租户管理</span>
        </el-menu-item>

        
        <el-divider class="sidebar-divider" />

        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Tools /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </template>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePermission } from '@/composables/usePermission'
import { Collection, ChatDotRound, Setting, OfficeBuilding, HomeFilled, User, Tools, UserFilled, Cpu, Reading, Compass, EditPen, DataAnalysis, List } from '@element-plus/icons-vue'
import TenantSwitcher from './TenantSwitcher.vue'

const route = useRoute()
const authStore = useAuthStore()
const { canManageWorkspace, canManageMembers, canCreateWorkspace } = usePermission()

const props = defineProps<{ mobileOpen?: boolean }>()
const emit = defineEmits<{ (event: 'close-mobile'): void }>()

function handleSelect() {
  if (props.mobileOpen) emit('close-mobile')
}

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/') return '/'
  if (path.startsWith('/workbench')) return '/workbench'
  if (path.startsWith('/tasks')) return '/tasks'
  if (path.startsWith('/assets')) return '/assets'
  if (path.startsWith('/knowledge/network')) return '/knowledge/network'
  if (path.startsWith('/knowledge')) return '/knowledge'
  if (path.startsWith('/research')) return '/research'
  if (path.startsWith('/agents')) return '/agents'
  if (path.startsWith('/content')) return '/content'
  if (path.startsWith('/data-center')) return '/data-center'
  if (path.startsWith('/runs')) return '/runs'
  if (path.startsWith('/tenants')) return '/tenants'
  if (path.startsWith('/users')) return '/users'
  if (path.startsWith('/workspaces')) return '/workspaces'
  if (path.startsWith('/datasets')) return '/datasets'
  if (path.startsWith('/chat')) return '/chat'
  if (path.startsWith('/profile')) return '/profile'
  if (path.startsWith('/settings')) return '/settings'
  return path
})
</script>

<style scoped lang="scss">
.sidebar-container {
  height: 100vh;
  width: var(--sidebar-width, 248px);
  min-width: var(--sidebar-width, 248px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.82);
  border-right: 1px solid rgba(62, 42, 108, 0.08);
  box-shadow: 10px 0 30px rgba(62, 42, 108, 0.035);
  transition: transform 0.24s ease;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-x: hidden;
  overflow-y: auto;
  background: transparent;

  .logo {
    height: 84px;
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 0 24px;
    color: #201a2c;
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -0.02em;
    border-bottom: 1px solid rgba(62, 42, 108, 0.07);
    background: transparent;

    .el-icon {
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      color: white;
      background: linear-gradient(145deg, #8d5cf6, #5b32bd);
      border-radius: 11px;
      box-shadow: 0 7px 16px rgba(116, 65, 232, 0.24);
    }
  }

  .sidebar-divider {
    margin: 10px 16px;
    border-color: rgba(148, 163, 184, 0.26);
  }
}

.menu-section-label {
  margin: 16px 24px 5px;
  color: #aaa1b6;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .16em;
  line-height: 1;
  text-transform: uppercase;
}

:deep(.el-menu-item) {
  margin: 3px 14px;
  border-radius: 12px;
  height: 44px;
  line-height: 44px;
  transition: all 0.2s ease;
  color: #6f6a78;
  font-size: 14px;

  &:hover {
    background-color: #f6f1ff !important;
    color: #6330d1 !important;
  }

  &.is-active {
    background: #f0e8ff !important;
    color: #5d2cb6 !important;
    font-weight: 600;
  }
}

:deep(.el-menu-item .el-icon) { color: #8c8696; }
:deep(.el-menu-item.is-active .el-icon) { color: #6330d1; }

:global(html.dark) .menu-section-label { color: #8993a8; }

:global(html.dark) .sidebar-container {
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.96) 0%, rgba(15, 23, 42, 0.96) 100%);
  border-right-color: rgba(148, 163, 184, 0.16);
  box-shadow: 6px 0 24px rgba(2, 6, 23, 0.35);
}

:global(html.dark) .sidebar-menu .logo {
  border-bottom-color: rgba(148, 163, 184, 0.16);
  background: linear-gradient(90deg, rgba(124, 77, 200, 0.18), rgba(167, 139, 250, 0.12));
}

:global(html.dark) :deep(.el-menu-item) {
  &:hover {
    background-color: rgba(167, 139, 250, 0.14) !important;
    color: #ddd6fe !important;
  }

  &.is-active {
    background: linear-gradient(90deg, rgba(124, 77, 200, 0.30), rgba(167, 139, 250, 0.22)) !important;
    color: #ede9fe !important;
  }
}

@media (max-width: 768px) {
  .sidebar-container {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 1001;
    width: min(280px, 86vw);
    min-width: min(280px, 86vw);
    transform: translateX(-105%);
    box-shadow: 18px 0 42px rgba(45, 26, 85, 0.22);
  }

  .sidebar-container.is-mobile-open {
    transform: translateX(0);
  }
}
</style>
