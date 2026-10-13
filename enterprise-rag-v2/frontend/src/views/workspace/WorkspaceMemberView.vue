<template>
  <div class="workspace-member-list">
    <div class="header">
      <div>
        <p class="eyebrow">WORKSPACE · MEMBERS</p>
        <h1>成员管理</h1>
        <p class="subtitle">控制谁可以查看、编辑和管理当前工作空间的知识与生产内容。</p>
      </div>
      <el-button
        type="primary"
        @click="showAddDialog = true"
      >
        <el-icon><Plus /></el-icon>
        添加成员
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="members"
      stripe
    >
      <el-table-column
        prop="user.username"
        label="用户名"
        min-width="120"
      />
      <el-table-column
        prop="user.email"
        label="邮箱"
        min-width="200"
      />
      <el-table-column
        label="角色"
        width="120"
      >
        <template #default="{ row }">
          <el-tag :type="getRoleType(row.role)">
            {{ getRoleLabel(row.role) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="加入时间"
        width="180"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="180"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            link
            @click="openEditDialog(row)"
          >
            编辑角色
          </el-button>
          <el-button
            type="danger"
            size="small"
            link
            @click="handleRemove(row)"
          >
            移除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加成员对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="添加成员"
      width="500px"
    >
      <el-form
        :model="addForm"
        label-width="100px"
      >
        <el-form-item
          label="用户ID"
          required
        >
          <el-input
            v-model="addForm.user_id"
            placeholder="请输入用户ID"
          />
        </el-form-item>
        <el-form-item
          label="角色"
          required
        >
          <el-select
            v-model="addForm.role"
            placeholder="请选择角色"
            style="width: 100%;"
          >
            <el-option
              label="所有者"
              value="owner"
            />
            <el-option
              label="管理员"
              value="admin"
            />
            <el-option
              label="成员"
              value="member"
            />
            <el-option
              label="查看者"
              value="viewer"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="handleAdd"
        >
          添加
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑角色对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑成员角色"
      width="500px"
    >
      <el-form
        :model="editForm"
        label-width="100px"
      >
        <el-form-item label="用户名">
          <el-input
            :model-value="editingMember?.user?.username"
            disabled
          />
        </el-form-item>
        <el-form-item
          label="角色"
          required
        >
          <el-select
            v-model="editForm.role"
            placeholder="请选择角色"
            style="width: 100%;"
          >
            <el-option
              label="所有者"
              value="owner"
            />
            <el-option
              label="管理员"
              value="admin"
            />
            <el-option
              label="成员"
              value="member"
            />
            <el-option
              label="查看者"
              value="viewer"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="handleEdit"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { workspaceApi } from '@/api/workspace'
import type { WorkspaceMember, WorkspaceMemberAdd, WorkspaceMemberUpdate } from '@/types/workspace'

const route = useRoute()
const router = useRouter()

const workspaceId = ref(route.params.id as string)
const loading = ref(false)
const saving = ref(false)
const members = ref<WorkspaceMember[]>([])
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const editingMember = ref<WorkspaceMember | null>(null)

const addForm = ref<WorkspaceMemberAdd>({
  user_id: '',
  role: 'member'
})

const editForm = ref<WorkspaceMemberUpdate>({
  role: 'member'
})

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getRoleType = (role: string) => {
  const types: Record<string, any> = {
    owner: 'danger',
    admin: 'warning',
    member: 'primary',
    viewer: 'info'
  }
  return types[role] || ''
}

const getRoleLabel = (role: string) => {
  const labels: Record<string, string> = {
    owner: '所有者',
    admin: '管理员',
    member: '成员',
    viewer: '查看者'
  }
  return labels[role] || role
}

const fetchMembers = async () => {
  loading.value = true
  try {
    members.value = await workspaceApi.listMembers(workspaceId.value)
  } catch (e: any) {
    ElMessage.error(e.message || '获取成员列表失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = async () => {
  if (!addForm.value.user_id.trim()) {
    ElMessage.warning('请输入用户ID')
    return
  }
  saving.value = true
  try {
    await workspaceApi.addMember(workspaceId.value, addForm.value)
    ElMessage.success('添加成功')
    showAddDialog.value = false
    addForm.value = { user_id: '', role: 'member' }
    await fetchMembers()
  } catch (e: any) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    saving.value = false
  }
}

const openEditDialog = (member: WorkspaceMember) => {
  editingMember.value = member
  editForm.value = { role: member.role }
  showEditDialog.value = true
}

const handleEdit = async () => {
  if (!editingMember.value) return
  saving.value = true
  try {
    await workspaceApi.updateMember(workspaceId.value, editingMember.value.user_id, editForm.value)
    ElMessage.success('更新成功')
    showEditDialog.value = false
    await fetchMembers()
  } catch (e: any) {
    ElMessage.error(e.message || '更新失败')
  } finally {
    saving.value = false
  }
}

const handleRemove = async (member: WorkspaceMember) => {
  try {
    await ElMessageBox.confirm(
      `确定要移除成员「${member.user?.username || member.user_id}」吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await workspaceApi.removeMember(workspaceId.value, member.user_id)
    ElMessage.success('移除成功')
    await fetchMembers()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '移除失败')
    }
  }
}

onMounted(() => {
  if (workspaceId.value) {
    fetchMembers()
  }
})
</script>

<style scoped lang="scss">
.workspace-member-list {
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
