<template>
  <div class="profile-view">
    <div class="page-intro">
      <span class="section-kicker">PERSONAL ACCOUNT</span>
      <h1>个人中心</h1>
      <p>查看账户信息、修改密码，并管理个人工作台身份。</p>
    </div>
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>个人中心</span>
        </div>
      </template>
      
      <div class="profile-content">
        <div class="avatar-section">
          <el-avatar
            :size="100"
            class="user-avatar"
          >
            {{ authStore.user?.name?.charAt(0)?.toUpperCase() || authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
          </el-avatar>
          <div class="avatar-actions">
            <el-button
              type="primary"
              size="small"
              disabled
            >
              更换头像
            </el-button>
          </div>
        </div>

        <el-form
          label-width="100px"
          class="profile-form"
        >
          <el-form-item label="用户名">
            <el-input
              :value="authStore.user?.name || authStore.user?.username || ''"
              disabled
            />
          </el-form-item>

          <el-form-item label="邮箱">
            <el-input
              :value="authStore.user?.email || ''"
              disabled
            />
          </el-form-item>

          <el-form-item label="注册时间">
            <el-input
              :value="formatDate(authStore.user?.created_at)"
              disabled
            />
          </el-form-item>
        </el-form>
      </div>
    </el-card>

    <el-card class="password-card">
      <template #header>
        <div class="card-header">
          <span>修改密码</span>
        </div>
      </template>

      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item
          label="当前密码"
          prop="old_password"
        >
          <el-input
            v-model="passwordForm.old_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
          />
        </el-form-item>

        <el-form-item
          label="新密码"
          prop="new_password"
        >
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            placeholder="请输入新密码（至少8位）"
            show-password
          />
        </el-form-item>

        <el-form-item
          label="确认密码"
          prop="confirm_password"
        >
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="passwordLoading"
            @click="handleChangePassword"
          >
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDate } from '@/utils/format'
import type { FormInstance, FormRules } from 'element-plus'
import request from '@/api/request'

const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const passwordFormRef = ref<FormInstance>()
const passwordLoading = ref(false)

const form = reactive({
  name: '',
  email: ''
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const rules: FormRules = {}

const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  old_password: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

onMounted(() => {
  // console.log('ProfileView mounted, authStore.user:', authStore.user)
  if (authStore.user) {
    form.name = authStore.user.name || authStore.user.username || ''
    form.email = authStore.user.email || ''
  }
})

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        await ElMessageBox.confirm('确定要修改密码吗？', '提示', {
          type: 'warning'
        })
        
        passwordLoading.value = true
        try {
          await request.post('/api/v1/auth/change-password', {
            old_password: passwordForm.old_password,
            new_password: passwordForm.new_password
          })
          
          ElMessage.success('密码修改成功，请重新登录')
          authStore.logout()
        } finally {
          passwordLoading.value = false
        }
      } catch (e: any) {
        if (e !== 'cancel') {
          ElMessage.error(e.message || '密码修改失败')
        }
      }
    }
  })
}
</script>

<style scoped lang="scss">
@use '@/styles/tokens/colors' as *;
@use '@/styles/tokens/spacing' as *;
@use '@/styles/tokens/radius' as *;
@use '@/styles/tokens/shadows' as *;
@use '@/styles/tokens/transitions' as *;

.profile-view {
  display: flex;
  flex-direction: column;
  gap: $spacing-6;
  max-width: 800px;
  width: 100%;
  --card-bg: rgba(255, 255, 255, 0.9);
  --card-border: rgba(148, 163, 184, 0.2);

  .page-intro {
    .section-kicker {
      color: var(--el-color-primary);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .16em;
    }

    h1 {
      margin: 7px 0 6px;
      color: #2e2240;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(32px, 4vw, 46px);
      letter-spacing: -.045em;
    }

    p {
      margin: 0;
      color: var(--el-text-color-secondary);
    }
  }

  .profile-card,
  .password-card {
    border-radius: 16px;
    border: 1px solid var(--card-border);
    background: var(--card-bg);
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
    backdrop-filter: blur(8px);
    transition: box-shadow 0.3s ease, border-color 0.3s ease;

    &:hover {
      box-shadow: 0 16px 30px rgba(15, 23, 42, 0.1);
      border-color: rgba(124, 77, 200, 0.35);
    }

    .card-header {
      font-weight: 600;
      font-size: 16px;
      color: var(--el-text-color-primary, #{$color-text-primary});
      display: flex;
      align-items: center;
      gap: 8px;

      &::before {
        content: '';
        width: 4px;
        height: 18px;
        background: linear-gradient(135deg, var(--el-color-primary) 0%, var(--el-color-primary-dark-2) 100%);
        border-radius: 2px;
      }
    }
  }

  .profile-content {
    display: flex;
    flex-direction: column;
    gap: $spacing-6;

    .avatar-section {
      display: flex;
      align-items: center;
      gap: $spacing-6;
      padding-bottom: $spacing-6;
      margin-bottom: $spacing-6;
      border-bottom: 1px solid var(--el-border-color-lighter, #{$color-border-secondary});

      .user-avatar {
        background: linear-gradient(135deg, var(--el-color-primary-light-3) 0%, var(--el-color-primary) 100%);
        font-size: 36px;
        font-weight: 600;
        color: #fff;
        flex-shrink: 0;
        transition: transform 0.3s ease;
        cursor: pointer;

        &:hover {
          transform: scale(1.05);
        }
      }

      .user-info {
        flex: 1;

        .user-name {
          font-size: 20px;
          font-weight: 600;
          color: var(--el-text-color-primary, #{$color-text-primary});
          margin-bottom: 4px;
        }

        .user-role {
          font-size: 14px;
          color: var(--el-text-color-secondary, #{$color-text-tertiary});
          padding: 2px 8px;
          background-color: var(--el-color-primary-light-9, rgba(33, 150, 243, 0.08));
          border-radius: $radius-sm;
          font-weight: 500;
        }
      }

      .avatar-actions {
        display: flex;
        gap: $spacing-3;

        .el-button {
          border-radius: 10px;
        }
      }
    }

    .profile-form {
      max-width: 500px;

      :deep(.el-form-item__label) {
        color: var(--el-text-color-regular, #{$color-text-secondary});
        font-weight: 500;
      }

      :deep(.el-input.is-disabled .el-input__wrapper) {
        background-color: var(--el-fill-color-extra-light, #fafafa);
        opacity: 0.85;
      }
    }
  }

  // Responsive design
  @media (max-width: 768px) {
    max-width: 100%;
    padding: 0 $spacing-4;

    .profile-content {
      .avatar-section {
        flex-direction: column;
        text-align: center;

        .user-info {
          text-align: center;
        }

        .avatar-actions {
          justify-content: center;
        }
      }

      .profile-form {
        max-width: 100%;
      }
    }
  }
}

// Dark mode specific styles
html.dark {
  .profile-view {
    --card-bg: rgba(30, 41, 59, 0.72);
    --card-border: rgba(148, 163, 184, 0.2);

    .profile-card,
    .password-card {
      &:hover {
        box-shadow: 0 16px 30px rgba(2, 6, 23, 0.38);
      }
    }

    .profile-content {
      .avatar-section {
        border-bottom-color: var(--el-border-color);

        .user-avatar {
          background: linear-gradient(135deg, rgba(144, 202, 249, 0.8) 0%, rgba(100, 181, 246, 1) 100%);
        }

        .user-info {
          .user-role {
            background-color: rgba(100, 181, 246, 0.12);
          }
        }
      }

      .profile-form {
        :deep(.el-input.is-disabled .el-input__wrapper) {
          background-color: var(--el-fill-color-darker);
        }
      }
    }
  }
}
</style>
