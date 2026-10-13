<template>
  <div class="main-layout">
    <AppSidebar
      :mobile-open="mobileSidebarOpen"
      @close-mobile="mobileSidebarOpen = false"
    />
    <div class="main-content">
      <AppHeader @toggle-sidebar="mobileSidebarOpen = !mobileSidebarOpen" />
      <div class="page-container">
        <router-view :key="`${route.fullPath}:${workspaceStore.currentWorkspaceId || 'none'}`" />
      </div>
    </div>

    <div
      v-if="mobileSidebarOpen"
      class="mobile-sidebar-backdrop"
      aria-hidden="true"
      @click="mobileSidebarOpen = false"
    />

    <FloatingAssistant v-if="!route.path.startsWith('/chat')" />

    <Teleport to="body">
      <div
        v-if="createDialogVisible"
        class="workspace-dialog-overlay"
        @click.self="createDialogVisible = false"
      >
        <div class="workspace-dialog-card">
          <h3 class="dialog-title">创建工作空间</h3>
          <el-form :model="createForm" label-width="80px">
            <el-form-item label="名称">
              <el-input
                v-model="createForm.name"
                placeholder="请输入工作空间名称"
              />
            </el-form-item>
            <el-form-item label="描述">
              <el-input
                v-model="createForm.description"
                type="textarea"
                :rows="3"
                placeholder="请输入工作空间描述"
              />
            </el-form-item>
          </el-form>
          <div class="dialog-footer">
            <el-button @click="createDialogVisible = false">
              取消
            </el-button>
            <el-button
              type="primary"
              :loading="creating"
              @click="handleCreateWorkspace"
            >
              创建
            </el-button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, provide, onMounted } from 'vue'
import AppSidebar from '@/components/common/AppSidebar.vue'
import AppHeader from '@/components/common/AppHeader.vue'
import FloatingAssistant from '@/components/common/FloatingAssistant.vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { ElMessage } from 'element-plus'
import { shouldSkipDuplicateErrorToast } from '@/api/request'

const workspaceStore = useWorkspaceStore()
const route = useRoute()

const createDialogVisible = ref(false)
const creating = ref(false)
const mobileSidebarOpen = ref(false)
const createForm = ref({ name: '', description: '' })

function openCreateWorkspaceDialog() {
  createForm.value = { name: '', description: '' }
  createDialogVisible.value = true
}

provide('openCreateWorkspaceDialog', openCreateWorkspaceDialog)

async function handleCreateWorkspace() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入工作空间名称')
    return
  }

  creating.value = true
  let created = false
  try {
    await workspaceStore.createWorkspace({
      name: createForm.value.name,
      description: createForm.value.description
    })
    ElMessage.success('创建成功')
    createForm.value = { name: '', description: '' }
    await workspaceStore.fetchWorkspaces()
    created = true
  } catch (error: any) {
    console.error('[MainLayout] handleCreateWorkspace failed:', error)
    if (!shouldSkipDuplicateErrorToast(error)) {
      ElMessage.error('创建失败')
    }
  } finally {
    creating.value = false
    if (created) createDialogVisible.value = false
  }
}

onMounted(async () => {
  const authStore = useAuthStore()
  await authStore.initialize()
})
</script>

<style scoped lang="scss">
.main-layout {
  display: flex;
  height: 100vh;
  background:
    radial-gradient(circle at 12% 10%, rgba(116, 65, 232, 0.08), transparent 32%),
    radial-gradient(circle at 92% 88%, rgba(238, 228, 255, 0.72), transparent 35%),
    var(--el-bg-color-page);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: visible;
  background-color: rgba(255, 255, 255, 0.42);
}

.page-container {
  flex: 1;
  overflow-y: auto;
  padding: 30px 36px 48px;
  background: transparent;
  color: var(--el-text-color-primary);
}

.mobile-sidebar-backdrop {
  display: none;
}

/* 原生 dialog overlay — 绕过 Element Plus，确保在最顶层 */
.workspace-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99999;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  isolation: isolate;
}

.workspace-dialog-card {
  position: relative;
  z-index: 1;
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 24px;
  width: 500px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.24);

  .dialog-title {
    margin: 0 0 20px;
    font-size: 18px;
    font-weight: 600;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--el-border-color-lighter);
  }
}

@media (max-width: 768px) {
  .main-layout {
    min-width: 0;
  }

  .main-content {
    min-width: 0;
    width: 100%;
  }

  .page-container {
    padding: 18px 14px 32px;
  }

  .mobile-sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(28, 19, 48, 0.38);
    backdrop-filter: blur(2px);
  }
}
</style>
