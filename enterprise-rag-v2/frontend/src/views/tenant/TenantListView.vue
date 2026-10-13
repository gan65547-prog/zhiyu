<template>
  <div class="tenant-list-view">
    <div class="header">
      <div>
        <p class="eyebrow">SYSTEM · TENANTS</p>
        <h1>租户管理</h1>
        <p class="subtitle">管理组织、初始管理员和运行状态，数据操作仍严格限定在当前系统权限内。</p>
      </div>
      <el-button
        type="primary"
        @click="showCreateDialog = true"
      >
        <el-icon><Plus /></el-icon>
        创建租户
      </el-button>
    </div>

    <el-table
      :data="tenantList"
      stripe
    >
      <el-table-column
        prop="name"
        label="租户名称"
        min-width="150"
      />
      <el-table-column
        prop="contact_email"
        label="联系邮箱"
        min-width="180"
      />
      <el-table-column
        prop="plan"
        label="历史计划字段"
        width="120"
      >
        <template #default="{ row }">
          <el-tag type="info">
            {{ row.plan }}（历史字段）
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="status"
        label="状态"
        width="100"
      >
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="created_at"
        label="创建时间"
        width="180"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="120"
        fixed="right"
      >
        <template #default="{ row }">
          <el-dropdown>
            <el-button
              size="small"
              type="primary"
            >
              操作 <el-icon class="el-icon--right">
                <ArrowDown />
              </el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="viewDetail(row.id)">
                  <el-icon><View /></el-icon> 查看
                </el-dropdown-item>
                <el-dropdown-item @click="editTenant(row)">
                  <el-icon><Edit /></el-icon> 编辑
                </el-dropdown-item>
                <el-dropdown-item @click="openResetPasswordDialog(row)">
                  <el-icon><Lock /></el-icon> 修改密码
                </el-dropdown-item>
                <el-dropdown-item
                  divided
                  style="color: #f56c6c;"
                  @click="confirmDelete(row)"
                >
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建租户对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建租户"
      width="600px"
    >
      <el-form
        :model="createForm"
        label-width="120px"
      >
        <el-divider content-position="left">
          租户信息
        </el-divider>
        <el-form-item
          label="租户名称"
          required
        >
          <el-input
            v-model="createForm.name"
            placeholder="请输入租户名称"
          />
        </el-form-item>
        <el-form-item
          label="联系邮箱"
          required
        >
          <el-input
            v-model="createForm.contact_email"
            placeholder="请输入联系邮箱"
          />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input
            v-model="createForm.contact_phone"
            placeholder="请输入联系电话"
          />
        </el-form-item>
        <el-divider content-position="left">
          初始管理员
        </el-divider>
        <el-form-item
          label="管理员用户名"
          required
        >
          <el-input
            v-model="createForm.admin_username"
            placeholder="请输入管理员用户名"
          />
        </el-form-item>
        <el-form-item
          label="管理员邮箱"
          required
        >
          <el-input
            v-model="createForm.admin_email"
            placeholder="请输入管理员邮箱"
          />
        </el-form-item>
        <el-form-item
          label="管理员密码"
          required
        >
          <el-input
            v-model="createForm.admin_password"
            type="password"
            placeholder="请输入密码（至少8位）"
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

    <!-- 显示初始管理员密码的密码对话框 -->
    <el-dialog
      v-model="showPasswordDialog"
      title="租户创建成功！"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      >
        请务必记住以下初始管理员账号密码！关闭对话框后将不再显示
      </el-alert>
      <el-descriptions
        :column="1"
        border
      >
        <el-descriptions-item label="租户名称">
          {{ createdTenantInfo?.name }}
        </el-descriptions-item>
        <el-descriptions-item label="管理员用户名">
          {{ createdTenantInfo?.admin_username }}
        </el-descriptions-item>
        <el-descriptions-item label="管理员邮箱">
          {{ createdTenantInfo?.admin_email }}
        </el-descriptions-item>
        <el-descriptions-item label="管理员密码">
          <el-input
            v-model="createdTenantInfo.admin_password"
            type="text"
            readonly
          >
            <template #suffix>
              <el-button @click="browserNavigator.clipboard.writeText(createdTenantInfo.admin_password)">
                复制
              </el-button>
            </template>
          </el-input>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button
          type="primary"
          @click="showPasswordDialog = false"
        >
          我已记住
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑租户对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑租户"
      width="600px"
    >
      <el-form
        :model="editForm"
        label-width="120px"
      >
        <el-form-item
          label="租户名称"
          required
        >
          <el-input
            v-model="editForm.name"
            placeholder="请输入租户名称"
          />
        </el-form-item>
        <el-form-item
          label="联系邮箱"
          required
        >
          <el-input
            v-model="editForm.contact_email"
            placeholder="请输入联系邮箱"
          />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input
            v-model="editForm.contact_phone"
            placeholder="请输入联系电话"
          />
        </el-form-item>
        <el-form-item
          label="状态"
          required
        >
          <el-select
            v-model="editForm.status"
            placeholder="请选择状态"
          >
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
        <el-button @click="showEditDialog = false">
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Lock, ArrowDown, View, Delete } from '@element-plus/icons-vue'
import { getTenantList, createTenant, deleteTenant, updateTenant, type Tenant, type TenantCreate } from '@/api/tenant'
import { userApi } from '@/api/users'

const browserNavigator = globalThis.navigator
const router = useRouter()
const creating = ref(false)
const saving = ref(false)
const resettingPassword = ref(false)
const tenantList = ref<Tenant[]>([])
const showCreateDialog = ref(false)
const showPasswordDialog = ref(false)
const showEditDialog = ref(false)
const showResetPasswordDialog = ref(false)
const createdTenantInfo = ref<any>(null)
const currentTenant = ref<Tenant | null>(null)
const adminUser = ref<any>(null)
const createForm = ref<TenantCreate>({
  name: '',
  contact_email: '',
  contact_phone: '',
  admin_username: '',
  admin_email: '',
  admin_password: ''
})
const editForm = ref({
  name: '',
  contact_email: '',
  contact_phone: '',
  status: 'active'
})
const resetPasswordForm = ref({
  new_password: '',
  send_email: false
})

onMounted(() => {
  loadTenants()
})

const loadTenants = async () => {
  try {
    const response: any = await getTenantList()
    console.log('Tenant list response:', response)
    tenantList.value = response.data || []
  } catch (error: any) {
    console.error('Error loading tenants:', error)
    ElMessage.error('加载租户列表失败: ' + (error.response?.data?.detail || error.message))
  }
}

const handleCreate = async () => {
  if (!createForm.value.name || !createForm.value.contact_email || 
      !createForm.value.admin_username || !createForm.value.admin_email || 
      !createForm.value.admin_password) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (createForm.value.admin_password.length < 8) {
    ElMessage.warning('管理员密码至少需要8位')
    return
  }
  
  // 验证密码强度：至少包含一个大写字母、一个小写字母和一个数字
  const hasUpper = /[A-Z]/.test(createForm.value.admin_password)
  const hasLower = /[a-z]/.test(createForm.value.admin_password)
  const hasDigit = /[0-9]/.test(createForm.value.admin_password)
  
  if (!hasUpper || !hasLower || !hasDigit) {
    ElMessage.warning('管理员密码必须包含至少一个大写字母、一个小写字母和一个数字')
    return
  }
  
  creating.value = true
  try {
    const result = await createTenant(createForm.value)
    // 保存创建的租户信息和密码
    createdTenantInfo.value = {
      name: createForm.value.name,
      admin_username: createForm.value.admin_username,
      admin_email: createForm.value.admin_email,
      admin_password: createForm.value.admin_password
    }
    showPasswordDialog.value = true
    showCreateDialog.value = false
    createForm.value = {
      name: '',
      contact_email: '',
      contact_phone: '',
          admin_username: '',
      admin_email: '',
      admin_password: ''
    }
    loadTenants()
  } catch (error) {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

const viewDetail = (id: string) => {
  router.push(`/tenants/${id}`)
}

const editTenant = (tenant: Tenant) => {
  currentTenant.value = tenant
  editForm.value = {
    name: tenant.name,
    contact_email: tenant.contact_email,
    contact_phone: tenant.contact_phone || '',
    status: tenant.status
  }
  showEditDialog.value = true
}

const confirmDelete = (tenant: Tenant) => {
  ElMessageBox.confirm(
    `确定要删除租户"${tenant.name}"吗？此操作将删除所有关联数据且无法恢复！`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteTenant(tenant.id)
      ElMessage.success('删除成功')
      loadTenants()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  })
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    active: 'success',
    suspended: 'warning',
    deleted: 'danger'
  }
  return types[status] || 'info'
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const handleSave = async () => {
  if (!editForm.value.name || !editForm.value.contact_email) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  saving.value = true
  try {
    if (!currentTenant.value) {
      ElMessage.error('租户信息不存在')
      return
    }
    
    await updateTenant(currentTenant.value.id, editForm.value)
    ElMessage.success('保存成功')
    showEditDialog.value = false
    loadTenants()
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
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
  
  // 验证密码强度：至少包含一个大写字母、一个小写字母和一个数字
  const hasUpper = /[A-Z]/.test(resetPasswordForm.value.new_password)
  const hasLower = /[a-z]/.test(resetPasswordForm.value.new_password)
  const hasDigit = /[0-9]/.test(resetPasswordForm.value.new_password)
  
  if (!hasUpper || !hasLower || !hasDigit) {
    ElMessage.warning('密码必须包含至少一个大写字母、一个小写字母和一个数字')
    return
  }
  
  resettingPassword.value = true
  try {
    if (!adminUser.value?.id) {
      ElMessage.error('管理员信息不存在')
      return
    }
    
    await userApi.resetPassword(adminUser.value.id, {
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

const openResetPasswordDialog = (tenant: Tenant) => {
  // 这里简化处理，实际应该从租户详情中获取管理员信息
  // 为了演示，我们假设管理员信息可以从租户对象中获取
  adminUser.value = tenant.admin_info
  if (!adminUser.value) {
    ElMessage.warning('该租户没有管理员信息')
    return
  }
  showResetPasswordDialog.value = true
}
</script>

<style scoped>
.tenant-list-view {
  max-width: 1440px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 20px;
}

.header h1 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-family: Georgia, 'Times New Roman', serif;
  font-size: clamp(32px, 4vw, 48px);
  letter-spacing: -.045em;
}

.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 11px; font-weight: 800; letter-spacing: .16em; }
.subtitle { max-width: 680px; margin: 8px 0 0; color: var(--el-text-color-secondary); line-height: 1.7; }
:deep(.el-table) { overflow: hidden; border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; background: rgba(255,255,255,.88); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
:deep(.el-table th.el-table__cell) { background: #faf8ff; color: var(--el-text-color-secondary); }
:deep(.el-table tr), :deep(.el-table td.el-table__cell) { background: transparent; }
:deep(.el-table__inner-wrapper::before) { display: none; }
@media (max-width: 680px) { .header { flex-direction: column; } }
</style>
