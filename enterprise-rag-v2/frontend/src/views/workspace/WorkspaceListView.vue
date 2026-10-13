<template>
  <div class="workspace-list">
    <div class="header">
      <div>
        <p class="eyebrow">WORKSPACE · COLLABORATION</p>
        <h1>工作空间</h1>
        <p class="subtitle">把团队成员、知识库和生产任务放在同一个可切换的工作上下文中。</p>
      </div>
      <el-button
        v-if="canCreateWorkspace"
        type="primary"
        @click="showCreateDialog = true"
      >
        <el-icon><Plus /></el-icon>
        创建工作空间
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="workspaces"
      stripe
    >
      <el-table-column
        prop="name"
        label="名称"
        min-width="120"
      />
      <el-table-column
        prop="description"
        label="描述"
        min-width="200"
      />
      <el-table-column
        prop="dataset_count"
        label="数据集"
        width="100"
        align="center"
      />
      <el-table-column
        prop="member_count"
        label="成员"
        width="100"
        align="center"
      />
      <el-table-column
        label="创建时间"
        width="180"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="250"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            link
            @click="switchToWorkspace(row)"
          >
            切换
          </el-button>
          <el-button
            v-if="canManageMembers"
            type="primary"
            size="small"
            link
            @click="goToMembers(row)"
          >
            成员管理
          </el-button>
          <el-button
            v-if="canDeleteWorkspace"
            type="danger"
            size="small"
            link
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="showCreateDialog"
      title="创建工作空间"
      width="500px"
      append-to-body
      :z-index="3000"
    >
      <el-form
        :model="createForm"
        label-width="80px"
      >
        <el-form-item
          label="名称"
          required
        >
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
      <template #footer>
        <el-button @click="showCreateDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="creating"
          @click="handleCreate"
        >
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { shouldSkipDuplicateErrorToast } from '@/api/request'
import { useWorkspaceStore } from '@/stores/workspace'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const { canManageWorkspace, canDeleteWorkspace, canManageMembers, canCreateWorkspace } = usePermission()

const loading = ref(false)
const creating = ref(false)
const showCreateDialog = ref(false)
const workspaces = ref<any[]>([])

const createForm = ref({
  name: '',
  description: ''
})

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchWorkspaces = async () => {
  loading.value = true
  try {
    await workspaceStore.fetchWorkspaces()
    workspaces.value = workspaceStore.workspaces
  } catch (e: any) {
    if (!shouldSkipDuplicateErrorToast(e)) {
      ElMessage.error(e.message || '获取工作空间列表失败')
    }
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入工作空间名称')
    return
  }
  creating.value = true
  let created = false
  try {
    await workspaceStore.createWorkspace(createForm.value)
    ElMessage.success('创建成功')
    createForm.value = { name: '', description: '' }
    await fetchWorkspaces()
    created = true
  } catch (e: any) {
    console.error('[WorkspaceListView] handleCreate failed:', e)
    if (!shouldSkipDuplicateErrorToast(e)) {
      ElMessage.error(e.message || '创建失败')
    }
  } finally {
    creating.value = false
    if (created) showCreateDialog.value = false
  }
}

const handleDelete = async (workspace: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除工作空间「${workspace.name}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
    await workspaceStore.deleteWorkspace(workspace.id)
    ElMessage.success('删除成功')
    await fetchWorkspaces()
  } catch (e: any) {
    if (e !== 'cancel' && !shouldSkipDuplicateErrorToast(e)) {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

const switchToWorkspace = async (workspace: any) => {
  try {
    await workspaceStore.switchWorkspace(workspace.id)
    ElMessage.success(`已切换到「${workspace.name}」`)
  } catch (e: any) {
    if (!shouldSkipDuplicateErrorToast(e)) {
      ElMessage.error(e.message || '切换失败')
    }
  }
}

const goToMembers = (workspace: any) => {
  router.push(`/workspaces/${workspace.id}/members`)
}

onMounted(() => {
  fetchWorkspaces()
})
</script>

<style scoped lang="scss">
.workspace-list {
  max-width: 1440px;
  margin: 0 auto;

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 24px;

    h1 {
      margin: 0;
      color: var(--el-text-color-primary);
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(32px, 4vw, 48px);
      letter-spacing: -.045em;
    }
  }

  .eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 11px; font-weight: 800; letter-spacing: .16em; }
  .subtitle { max-width: 680px; margin: 8px 0 0; color: var(--el-text-color-secondary); line-height: 1.7; }
  :deep(.el-table) { overflow: hidden; border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; background: rgba(255,255,255,.88); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
  :deep(.el-table th.el-table__cell) { background: #faf8ff; color: var(--el-text-color-secondary); }
  :deep(.el-table tr), :deep(.el-table td.el-table__cell) { background: transparent; }
  :deep(.el-table__inner-wrapper::before) { display: none; }
  @media (max-width: 680px) { .header { flex-direction: column; } }
}
</style>
