<template>
  <div class="tenant-detail-view">
    <el-page-header
      title="返回"
      @back="handleBack"
    >
      <template #content>
        <span class="page-title">租户详情</span>
      </template>
    </el-page-header>

    <el-empty
      v-if="!tenant"
      description="加载中..."
    />

    <template v-else-if="tenant">
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <span>基本信息</span>
            <div>
              <el-button
                type="primary"
                size="small"
                @click="handleEdit"
              >
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button
                v-if="tenant?.admin_info && authStore.isSuperuser"
                type="warning"
                size="small"
                style="margin-left: 10px;"
                @click="showResetPasswordDialog = true"
              >
                <el-icon><Lock /></el-icon>
                修改管理员密码
              </el-button>
            </div>
          </div>
        </template>

        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="租户名称">
            {{ tenant.name }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(tenant.status)">
              {{ getStatusText(tenant.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="套餐">
            <el-tag type="info">{{ tenant.plan }}（历史字段）</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="联系邮箱">
            {{ tenant.contact_email }}
          </el-descriptions-item>
          <el-descriptions-item label="联系电话">
            {{ tenant.contact_phone || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(tenant.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="tenant.admin_info"
            label="初始管理员用户名"
          >
            {{ tenant.admin_info.username }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="tenant.admin_info"
            label="初始管理员邮箱"
          >
            {{ tenant.admin_info.email }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card
        v-if="!authStore.isSuperuser"
        class="workspaces-card"
      >
        <template #header>
          <span>工作空间列表</span>
        </template>
        <el-table
          :data="workspaces"
          stripe
        >
          <el-table-column
            prop="name"
            label="名称"
          />
          <el-table-column
            prop="description"
            label="描述"
          />
          <el-table-column label="创建时间">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="150"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                @click="viewWorkspace(row.id)"
              >
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-dialog
      v-model="editDialogVisible"
      title="编辑租户"
      width="600px"
    >
      <el-form
        :model="editForm"
        label-width="100px"
      >
        <el-form-item label="租户名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="联系邮箱">
          <el-input v-model="editForm.contact_email" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="editForm.contact_phone" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status">
            <el-option
              label="活跃"
              value="active"
            />
            <el-option
              label="停用"
              value="suspended"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="handleSave"
        >
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置管理员密码对话框 -->
    <el-dialog
      v-model="showResetPasswordDialog"
      title="修改租户管理员密码"
      width="500px"
    >
      <el-form
        :model="resetPasswordForm"
        label-width="120px"
      >
        <el-form-item label="新密码">
          <el-input
            v-model="resetPasswordForm.new_password"
            type="password"
            placeholder="请输入新密码（至少8位）"
          />
        </el-form-item>
        <el-form-item label="发送邮件">
          <el-switch v-model="resetPasswordForm.send_email" />
          <span style="margin-left: 10px; font-size: 12px; color: #999;">
            勾选后将向管理员邮箱发送密码重置通知
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResetPasswordDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="resettingPassword"
          @click="handleResetPassword"
        >
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit, Lock } from '@element-plus/icons-vue'
import { getTenantDetail, updateTenant } from '@/api/tenant'
import { getWorkspaceList } from '@/api/workspace'
import { userApi } from '@/api/users'
import { formatDateTime } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const saving = ref(false)
const resettingPassword = ref(false)
const tenant = ref<any>(null)
const workspaces = ref<any[]>([])
const editDialogVisible = ref(false)
const showResetPasswordDialog = ref(false)
const resetPasswordForm = ref({
  new_password: '',
  send_email: false
})
const editForm = ref({
  name: '',
  contact_email: '',
  contact_phone: '',
  status: ''
})

onMounted(async () => {
  await loadTenantDetail()
  if (!authStore.isSuperuser) {
    await loadWorkspaces()
  }
})

const loadTenantDetail = async () => {
  try {
    const tenantId = route.params.id as string
    const response = await getTenantDetail(tenantId)
    console.log('Tenant API response:', response)
    // 确保正确处理响应数据结构
    if (response.data?.data) {
      tenant.value = response.data.data
    } else if (response.data) {
      tenant.value = response.data
    } else {
      tenant.value = response
    }
    console.log('Processed tenant data:', tenant.value)
  } catch (error: any) {
    ElMessage.error('加载租户详情失败: ' + (error.response?.data?.detail || error.message))
  }
}

const loadWorkspaces = async () => {
  try {
    const tenantId = route.params.id as string
    const response = await getWorkspaceList({ tenant_id: tenantId })
    workspaces.value = response.data.data.items || []
  } catch (error: any) {
    ElMessage.error('加载工作空间列表失败: ' + (error.response?.data?.detail || error.message))
  }
}

const handleBack = () => {
  router.back()
}

const handleEdit = () => {
  editForm.value = {
    name: tenant.value.name,
    contact_email: tenant.value.contact_email,
    contact_phone: tenant.value.contact_phone || '',
    status: tenant.value.status
  }
  editDialogVisible.value = true
}

const handleSave = async () => {
  saving.value = true
  try {
    const tenantId = route.params.id as string
    await updateTenant(tenantId, editForm.value)
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    await loadTenantDetail()
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    active: 'success',
    suspended: 'warning',
    deleted: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    active: '活跃',
    suspended: '停用',
    deleted: '已删除'
  }
  return texts[status] || status
}

const viewWorkspace = (workspaceId: string) => {
  router.push(`/workspaces/${workspaceId}`)
}

const handleResetPassword = async () => {
  if (!resetPasswordForm.value.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  
  if (resetPasswordForm.value.new_password.length < 8) {
    ElMessage.warning('密码至少需要8位')
    return
  }
  
  resettingPassword.value = true
  try {
    if (!tenant.value?.admin_info?.id) {
      ElMessage.error('管理员信息不存在')
      return
    }
    
    await userApi.resetPassword(tenant.value.admin_info.id, {
      new_password: resetPasswordForm.value.new_password,
      send_email: resetPasswordForm.value.send_email
    })
    
    ElMessage.success('密码重置成功')
    showResetPasswordDialog.value = false
    resetPasswordForm.value = {
      new_password: '',
      send_email: false
    }
  } catch (error: any) {
    ElMessage.error('密码重置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    resettingPassword.value = false
  }
}
</script>

<style scoped lang="scss">
.tenant-detail-view {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 600;
  }

  .info-card {
    margin-top: 20px;
  }

  .workspaces-card {
    margin-top: 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
