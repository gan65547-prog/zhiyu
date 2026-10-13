<template>
  <section class="user-list">
    <header class="page-header">
      <div>
        <p class="eyebrow">WORKSPACE ADMIN · MEMBERS</p>
        <h1>用户管理</h1>
        <p class="subtitle">管理当前租户成员、工作空间权限和账号状态。</p>
      </div>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        新建用户
      </el-button>
    </header>

    <div class="user-summary">
      <article><span>成员总数</span><strong>{{ users.length }}</strong><small>当前列表范围</small></article>
      <article class="green"><span>已激活</span><strong>{{ activeUserCount }}</strong><small>可正常登录</small></article>
      <article class="warm"><span>已停用</span><strong>{{ users.length - activeUserCount }}</strong><small>需要重新启用</small></article>
      <article class="accent"><span>管理员</span><strong>{{ adminUserCount }}</strong><small>拥有管理权限</small></article>
    </div>

    <el-card shadow="never" class="users-card">
      <template #header>
        <div class="card-header">
          <div><span class="section-kicker">MEMBER DIRECTORY</span><strong>成员目录</strong></div>
          <span class="card-note">工作空间权限异步同步</span>
        </div>
      </template>

      <!-- 搜索和筛选 -->
      <el-form
        :inline="true"
        :model="searchForm"
        class="search-form"
      >
        <el-form-item label="搜索">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索用户名或邮箱"
            clearable
            @clear="loadUsers"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.is_active"
            placeholder="全部"
            clearable
            @change="loadUsers"
          >
            <el-option
              label="激活"
              :value="true"
            />
            <el-option
              label="停用"
              :value="false"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="loadUsers"
          >
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 用户列表 -->
      <el-table
        v-loading="loading"
        :data="users"
        style="width: 100%"
      >
        <el-table-column
          prop="username"
          label="用户名"
          width="150"
        />
        <el-table-column
          prop="email"
          label="邮箱"
          min-width="200"
        />
        <el-table-column
          label="状态"
          width="100"
        >
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '激活' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="角色"
          width="120"
        >
          <template #default="{ row }">
            <el-tag
              v-if="row.is_superuser"
              type="danger"
            >
              超级管理员
            </el-tag>
            <el-tag
              v-else-if="isTenantAdmin(row)"
              type="warning"
            >
              租户管理员
            </el-tag>
            <el-tag
              v-else
              type="info"
            >
              普通用户
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="工作空间"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tag
              v-for="ws in (row.workspaces || [])"
              :key="ws.id"
              size="small"
              type="primary"
              effect="plain"
              style="margin-right: 4px; margin-bottom: 4px;"
            >
              {{ ws.name }}
            </el-tag>
            <span
              v-if="!(row.workspaces && row.workspaces.length)"
              class="text-gray-400"
            >无</span>
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
          width="280"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button 
              v-if="!row.is_superuser"
              link 
              type="warning" 
              size="small" 
              @click="handleResetPassword(row)"
            >
              重置密码
            </el-button>
            <el-button 
              v-if="!row.is_superuser"
              link 
              :type="row.is_active ? 'danger' : 'success'" 
              size="small" 
              @click="handleToggleActive(row)"
            >
              {{ row.is_active ? '停用' : '激活' }}
            </el-button>
            <el-popconfirm
              v-if="!row.is_superuser && !isCurrentUser(row.id)"
              title="确定要删除该用户吗？"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button
                  link
                  type="danger"
                  size="small"
                >
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="loadUsers"
        @current-change="loadUsers"
      />
    </el-card>

    <!-- 创建/编辑用户对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '创建用户'"
      width="500px"
      @close="resetForm"
    >
      <el-form
        ref="userFormRef"
        :model="userForm"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item
          label="用户名"
          prop="username"
        >
          <el-input
            v-model="userForm.username"
            :disabled="isEdit"
          />
        </el-form-item>
        <el-form-item
          label="邮箱"
          prop="email"
        >
          <el-input
            v-model="userForm.email"
            type="email"
          />
        </el-form-item>
        <el-form-item
          v-if="!isEdit"
          label="密码"
          prop="password"
        >
          <el-input
            v-model="userForm.password"
            type="password"
            show-password
          />
        </el-form-item>
        <el-form-item
          v-if="isEdit"
          label="状态"
          prop="is_active"
        >
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
        <el-form-item
          label="工作空间"
          prop="workspace_ids"
        >
          <el-select
            v-model="userForm.workspace_ids"
            multiple
            placeholder="选择用户可访问的工作空间"
            style="width: 100%"
          >
            <el-option
              v-for="ws in workspaceStore.workspaces"
              :key="ws.id"
              :label="ws.name"
              :value="ws.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          label="默认权限"
          prop="default_role"
        >
          <el-select
            v-model="userForm.default_role"
            style="width: 100%"
          >
            <el-option
              label="查看者"
              value="viewer"
            />
            <el-option
              label="成员"
              value="member"
            />
            <el-option
              label="管理员（可邀请管理员）"
              value="admin"
            />
            <el-option
              label="所有者"
              value="owner"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleSubmit"
        >
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="resetPasswordDialogVisible"
      title="重置密码"
      width="400px"
    >
      <el-form
        ref="resetPasswordFormRef"
        :model="resetPasswordForm"
        :rules="resetPasswordRules"
        label-width="100px"
      >
        <el-form-item
          label="新密码"
          prop="new_password"
        >
          <el-input
            v-model="resetPasswordForm.new_password"
            type="password"
            show-password
          />
        </el-form-item>
        <el-form-item
          label="确认密码"
          prop="confirm_password"
        >
          <el-input
            v-model="resetPasswordForm.confirm_password"
            type="password"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleResetPasswordSubmit"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { userApi } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import type { User, UserCreate, UserUpdate, UserResetPassword } from '@/types/user'
import type { FormInstance, FormRules } from 'element-plus'

const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()

// 状态
const loading = ref(false)
const users = ref<User[]>([])
const dialogVisible = ref(false)
const resetPasswordDialogVisible = ref(false)
const isEdit = ref(false)
const currentUser = ref<User | null>(null)
const workspacesLoading = ref(false)
let workspaceHydrationToken = 0

// 搜索表单
const searchForm = reactive({
  search: '',
  is_active: undefined as boolean | undefined
})

// 分页
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 用户表单
const userFormRef = ref<FormInstance>()
const userForm = reactive({
  username: '',
  email: '',
  password: '',
  is_active: true,
  workspace_ids: [] as string[],
  default_role: 'member' as 'owner' | 'admin' | 'member' | 'viewer'
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少 8 个字符', trigger: 'blur' }
  ]
}

// 重置密码表单
const resetPasswordFormRef = ref<FormInstance>()
const resetPasswordForm = reactive({
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (rule: any, value: any, callback: any) => {
  if (value !== resetPasswordForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const resetPasswordRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少 8 个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 计算当前用户
const isCurrentUser = (userId: string) => {
  return authStore.currentUser?.id === userId
}

const isTenantAdmin = (user: any) => {
  const roles = (user?.workspaces || []).map((w: any) => String(w?.role || '').toLowerCase())
  return roles.includes('owner') || roles.includes('admin')
}

const activeUserCount = computed(() => users.value.filter(user => user.is_active).length)
const adminUserCount = computed(() => users.value.filter(user => user.is_superuser || isTenantAdmin(user)).length)

const isVisibleUser = (user: User) => {
  return !user.is_superuser
}

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const result = await userApi.list({
      page: pagination.page,
      page_size: pagination.page_size,
      search: searchForm.search,
      is_active: searchForm.is_active
    })

    // 先展示用户基础列表，避免在问答流式期间因为 N+1 请求导致整页长时间 loading
    const hydrationToken = ++workspaceHydrationToken
    const visibleUsers = result.items.filter(isVisibleUser)
    users.value = visibleUsers.map((user: User) => ({
      ...user,
      workspaces: []
    }))
    pagination.total = visibleUsers.length

    // 后台异步补齐工作空间信息，不阻塞首屏渲染
    void hydrateUserWorkspaces(users.value, hydrationToken)
  } catch (error: any) {
    ElMessage.error(error.message || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const hydrateUserWorkspaces = async (userList: User[], hydrationToken: number) => {
  const usersWithWorkspaces = await Promise.all(userList.map(async (user: User) => {
    try {
      const workspacesResult = await userApi.getWorkspaces(user.id)
      let workspacesArray: any[] = []
      if (Array.isArray(workspacesResult)) {
        workspacesArray = workspacesResult
      } else if (workspacesResult?.data) {
        workspacesArray = Array.isArray(workspacesResult.data) ? workspacesResult.data : []
      }

      workspacesArray = workspacesArray.map(ws => {
        if (ws && typeof ws === 'object') {
          return {
            id: ws.workspace_id || ws.id,
            name: ws.workspace_name || ws.name,
            role: ws.role,
            is_default: ws.is_default,
            joined_at: ws.joined_at
          }
        }
        return null
      }).filter(Boolean)

      return {
        ...user,
        workspaces: workspacesArray
      }
    } catch (error) {
      console.error(`Failed to fetch workspaces for user ${user.id}:`, error)
      return {
        ...user,
        workspaces: []
      }
    }
  }))

  // 只更新最新一次 loadUsers 触发的结果，避免并发查询造成回写旧数据
  if (hydrationToken === workspaceHydrationToken) {
    users.value = usersWithWorkspaces
  }
}

// 创建用户
const handleCreate = async () => {
  isEdit.value = false
  resetForm()
  
  // 加载工作空间列表
  workspacesLoading.value = true
  try {
    await workspaceStore.fetchWorkspaces()
  } catch (error) {
    console.error('Failed to fetch workspaces:', error)
  } finally {
    workspacesLoading.value = false
  }
  
  dialogVisible.value = true
}

// 编辑用户
const handleEdit = async (user: User) => {
  isEdit.value = true
  currentUser.value = user
  userForm.username = user.username
  userForm.email = user.email
  userForm.is_active = user.is_active
  userForm.workspace_ids = []
  userForm.default_role = 'member'
  
  // 加载工作空间列表
  workspacesLoading.value = true
  try {
    await workspaceStore.fetchWorkspaces()
    
    // 获取用户的工作空间权限
    if (user.id) {
      try {
        // 直接调用API获取用户的工作空间权限，确保获取最新数据
        const workspacesResult = await userApi.getWorkspaces(user.id)
        let workspacesArray: any[] = []
        if (Array.isArray(workspacesResult)) {
          workspacesArray = workspacesResult
        } else if (workspacesResult?.data) {
          workspacesArray = Array.isArray(workspacesResult.data) ? workspacesResult.data : []
        }
        // 转换工作空间对象格式，将 workspace_id 改为 id
        userForm.workspace_ids = workspacesArray.map((ws: any) => ws.workspace_id || ws.id)
        const roles = workspacesArray
          .map((ws: any) => String(ws.role || '').toLowerCase())
          .filter(Boolean)
        if (roles.includes('owner')) userForm.default_role = 'owner'
        else if (roles.includes('admin')) userForm.default_role = 'admin'
        else if (roles.includes('member')) userForm.default_role = 'member'
        else if (roles.includes('viewer')) userForm.default_role = 'viewer'
      } catch (error) {
        console.error('Failed to fetch user workspaces:', error)
      }
    }
  } catch (error) {
    console.error('Failed to fetch workspaces:', error)
  } finally {
    workspacesLoading.value = false
  }
  
  dialogVisible.value = true
}

// 重置密码
const handleResetPassword = (user: User) => {
  currentUser.value = user
  resetPasswordForm.new_password = ''
  resetPasswordForm.confirm_password = ''
  resetPasswordDialogVisible.value = true
}

// 切换激活状态
const handleToggleActive = async (user: User) => {
  try {
    await userApi.activate(user.id, { is_active: !user.is_active })
    ElMessage.success(user.is_active ? '用户已停用' : '用户已激活')
    await loadUsers()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

// 删除用户
const handleDelete = async (user: User) => {
  try {
    await userApi.delete(user.id)
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (error: any) {
    ElMessage.error(error.message || '删除用户失败')
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!userFormRef.value) return
  
  try {
    await userFormRef.value.validate()
    let effectiveWorkspaceIds = [...userForm.workspace_ids]
    const fallbackWorkspaceId = workspaceStore.currentWorkspace?.id
    if (!effectiveWorkspaceIds.length && fallbackWorkspaceId) {
      // 避免“只改角色但未绑定工作空间”导致角色配置无效
      effectiveWorkspaceIds = [fallbackWorkspaceId]
      ElMessage.warning('未选择工作空间，已自动使用当前工作空间应用权限')
    }
    
    if (isEdit.value && currentUser.value) {
      const updateData: UserUpdate = {
        email: userForm.email,
        is_active: userForm.is_active,
        workspace_ids: effectiveWorkspaceIds,
        default_role: userForm.default_role
      }
      
      await userApi.update(currentUser.value.id, updateData)
      ElMessage.success('用户已更新')
    } else {
      const createData: UserCreate & { tenant_id?: string } = {
        username: userForm.username,
        email: userForm.email,
        password: userForm.password,
        is_active: userForm.is_active,
        workspace_ids: effectiveWorkspaceIds,
        default_role: userForm.default_role,
        tenant_id: authStore.currentUser?.tenant_id
      }
      await userApi.create(createData)
      ElMessage.success('用户已创建')
    }
    
    dialogVisible.value = false
    await loadUsers()
  } catch (error: any) {
    if (error !== false) {
      ElMessage.error(error.message || '操作失败')
    }
  }
}

// 重置密码提交
const handleResetPasswordSubmit = async () => {
  if (!resetPasswordFormRef.value || !currentUser.value) return
  
  try {
    await resetPasswordFormRef.value.validate()
    
    const data: UserResetPassword = {
      new_password: resetPasswordForm.new_password
    }
    await userApi.resetPassword(currentUser.value.id, data)
    ElMessage.success('密码已重置')
    resetPasswordDialogVisible.value = false
  } catch (error: any) {
    if (error !== false) {
      ElMessage.error(error.message || '重置密码失败')
    }
  }
}

// 重置表单
const resetForm = () => {
  userForm.username = ''
  userForm.email = ''
  userForm.password = ''
  userForm.is_active = true
  userForm.workspace_ids = []
  userForm.default_role = 'member'
  currentUser.value = null
  userFormRef.value?.resetFields()
}

// 格式化日期
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('zh-CN')
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped lang="scss">
.user-list {
  max-width: 1440px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.eyebrow, .section-kicker {
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .16em;
}

.eyebrow { margin: 0 0 8px; }

h1 {
  margin: 0 0 8px;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: clamp(32px, 4vw, 48px);
  letter-spacing: -.045em;
}

.subtitle { margin: 0; color: var(--el-text-color-secondary); line-height: 1.7; }

.user-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.user-summary article {
  display: flex;
  min-height: 104px;
  flex-direction: column;
  justify-content: space-between;
  padding: 16px 18px;
  border: 1px solid rgba(112, 74, 198, .13);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(249,247,255,.92));
  box-shadow: 0 12px 30px rgba(79,51,133,.05);
}

.user-summary article span, .user-summary article small, .card-note { color: var(--el-text-color-secondary); font-size: 12px; }
.user-summary article strong { color: #2d2140; font-family: Georgia, 'Times New Roman', serif; font-size: 30px; }
.user-summary .green { background: linear-gradient(145deg,#f2fbf6,#fff); }
.user-summary .green strong { color: #2f8a61; }
.user-summary .warm { background: linear-gradient(145deg,#fffaf0,#fff); }
.user-summary .warm strong { color: #b4771c; }
.user-summary .accent { background: linear-gradient(145deg,#eee6ff,#fff); }
.user-summary .accent strong { color: var(--el-color-primary); }

.users-card { border: 1px solid rgba(112,74,198,.13); border-radius: 18px; box-shadow: 0 12px 30px rgba(79,51,133,.05); }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.card-header > div { display: flex; flex-direction: column; gap: 5px; }

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) { .user-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .page-header { flex-direction: column; } .user-summary { grid-template-columns: 1fr 1fr; } }
</style>
