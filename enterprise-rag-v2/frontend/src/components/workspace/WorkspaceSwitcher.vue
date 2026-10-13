<template>
  <div class="workspace-switcher">
    <div
      class="current-workspace"
      @click="showDropdown = !showDropdown"
    >
      <div class="workspace-icon">
        <i class="pi pi-briefcase" />
      </div>
      <div class="workspace-info">
        <span class="workspace-name">{{ currentWorkspaceName }}</span>
        <span class="workspace-label">当前工作空间</span>
      </div>
      <i
        class="pi pi-chevron-down"
        :class="{ 'pi-chevron-up': showDropdown }"
      />
    </div>

    <div
      v-if="showDropdown"
      class="workspace-dropdown"
    >
      <div class="dropdown-header">
        <span>工作空间</span>
        <button
          class="btn-create"
          @click="showCreateDialog = true"
        >
          <i class="pi pi-plus" />
          新建
        </button>
      </div>

      <div class="workspace-list">
        <div
          v-for="workspace in workspaces"
          :key="workspace.id"
          class="workspace-item"
          :class="{ active: workspace.id === currentWorkspaceId }"
          @click="handleSwitch(workspace.id)"
        >
          <div class="workspace-icon-small">
            <i class="pi pi-briefcase" />
          </div>
          <div class="workspace-details">
            <span class="name">{{ workspace.name }}</span>
          </div>
          <i
            v-if="workspace.id === currentWorkspaceId"
            class="pi pi-check"
          />
        </div>
      </div>

      <div
        v-if="loading"
        class="loading-state"
      >
        <i class="pi pi-spinner pi-spin" />
        <span>加载中...</span>
      </div>

      <div
        v-else-if="workspaces.length === 0"
        class="empty-state"
      >
        <span>暂无工作空间</span>
      </div>
    </div>

    <el-dialog
      v-model="showCreateDialog"
      header="创建工作空间"
      :modal="true"
      :style="{ width: '450px' }"
    >
      <div class="create-form">
        <div class="form-group">
          <label for="workspaceName">名称</label>
          <el-input
            id="workspaceName"
            v-model="newWorkspace.name"
            placeholder="请输入工作空间名称"
            class="w-full"
          />
        </div>
        <div class="form-group">
          <label for="workspaceDesc">描述（可选）</label>
          <el-input
            id="workspaceDesc"
            v-model="newWorkspace.description"
            placeholder="请输入工作空间描述"
            :rows="3"
            type="textarea"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <el-button
          @click="showCreateDialog = false"
        >取消</el-button>
        <el-button
          :loading="creating"
          @click="handleCreate"
        >创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { shouldSkipDuplicateErrorToast } from '@/api/request'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const { workspaces, currentWorkspace, loading } = storeToRefs(workspaceStore)

const showDropdown = ref(false)
const showCreateDialog = ref(false)
const creating = ref(false)

const newWorkspace = reactive({
  name: '',
  description: ''
})

const currentWorkspaceName = computed(() => currentWorkspace.value?.name || '未选择工作空间')
const currentWorkspaceId = computed(() => currentWorkspace.value?.id)

onMounted(async () => {
  try {
    await workspaceStore.fetchWorkspaces()
    await workspaceStore.fetchCurrentWorkspace()
  } catch (error: any) {
    if (!shouldSkipDuplicateErrorToast(error)) {
      ElMessage.error(error.message || '加载工作空间失败')
    }
  }
})

async function handleSwitch(workspaceId: string) {
  if (workspaceId === currentWorkspaceId.value) {
    showDropdown.value = false
    return
  }

  try {
    await workspaceStore.switchWorkspace(workspaceId)
    showDropdown.value = false
    if (router.currentRoute.value.path !== '/datasets') {
      await router.push('/datasets')
    }
    ElMessage.success('工作空间已切换')
  } catch (error: any) {
    if (!shouldSkipDuplicateErrorToast(error)) {
      ElMessage.error(error.message || '切换工作空间失败')
    }
  }
}

async function handleCreate() {
  if (!newWorkspace.name.trim()) {
    ElMessage.warning('请输入工作空间名称')
    return
  }

  creating.value = true
  try {
    await workspaceStore.createWorkspace({
      name: newWorkspace.name,
      description: newWorkspace.description || undefined
    })
    newWorkspace.name = ''
    newWorkspace.description = ''
    ElMessage.success('工作空间创建成功')
  } catch (error: any) {
    console.error('[WorkspaceSwitcher] createWorkspace failed:', error)
    if (!shouldSkipDuplicateErrorToast(error)) {
      ElMessage.error(error.message || '创建工作空间失败')
    }
  } finally {
    creating.value = false
    showCreateDialog.value = false
  }
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.workspace-switcher')) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.workspace-switcher {
  position: relative;
}

.current-workspace {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.current-workspace:hover {
  background-color: var(--surface-hover);
}

.workspace-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--primary-color), var(--primary-color-light));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.workspace-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.workspace-name {
  font-weight: 500;
  color: var(--text-color);
}

.workspace-label {
  font-size: 12px;
  color: var(--text-color-secondary);
}

.workspace-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  min-width: 280px;
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-border);
  font-weight: 500;
}

.btn-create {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  background: var(--primary-color);
  color: white;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.workspace-list {
  max-height: 300px;
  overflow-y: auto;
}

.workspace-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.workspace-item:hover {
  background-color: var(--surface-hover);
}

.workspace-item.active {
  background-color: var(--primary-color-lightest);
}

.workspace-icon-small {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--surface-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-color-secondary);
}

.workspace-details {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.workspace-details .name {
  font-weight: 500;
}

.loading-state,
.empty-state {
  padding: 24px;
  text-align: center;
  color: var(--text-color-secondary);
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: 500;
  color: var(--text-color);
}
</style>
