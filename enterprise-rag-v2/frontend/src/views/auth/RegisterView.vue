<template>
  <div class="register-page">
    <div class="register-page__blur register-page__blur--left" />
    <div class="register-page__blur register-page__blur--right" />

    <div class="register-shell">
      <section class="register-brand">
        <div class="register-brand__tag">
          知域引擎 · DomainMind Engine
        </div>
        <h1>创建你的账号</h1>
        <p>一个人用免费。微信聊天记录、截图、文档 — 拖进来就能搜。</p>
      </section>

      <section class="register-card">
        <h2>账号注册</h2>
        <p class="register-card__hint">
          请填写基础信息，快速开通使用
        </p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="register-form"
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="name">
            <el-input
              v-model="form.name"
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>

          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱"
              size="large"
              :prefix-icon="Message"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码（至少8位）"
              size="large"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请确认密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleRegister"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="authStore.loading"
              class="submit-btn"
              @click="handleRegister"
            >
              注册
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <router-link to="/login">
              已有账号？立即登录
            </router-link>
          </div>
        </el-form>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { User, Message, Lock } from '@element-plus/icons-vue'
import { validateEmail, validatePassword } from '@/utils/validate'
import type { FormInstance } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { validator: (_rule: any, value: string, callback: any) => {
      if (!validateEmail(value)) {
        callback(new Error('邮箱格式不正确'))
      } else {
        callback()
      }
    }, trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: (_rule: any, value: string, callback: any) => {
      if (!validatePassword(value)) {
        callback(new Error('密码长度至少8位'))
      } else {
        callback()
      }
    }, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        await authStore.registerUser({
          name: form.name,
          email: form.email,
          password: form.password
        })
        router.push('/')
      } catch (e) {
        // error handled by interceptor
      }
    }
  })
}
</script>

<style scoped lang="scss">
.register-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at 15% 20%, rgba(112, 74, 198, 0.18), transparent 42%),
    radial-gradient(circle at 85% 80%, rgba(176, 145, 235, 0.2), transparent 40%),
    linear-gradient(135deg, #fbf9ff 0%, #f5efff 52%, #f1ebff 100%);
  overflow: hidden;
}

.register-page__blur {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.45;
  pointer-events: none;

  &.register-page__blur--left {
    top: -70px;
    left: -100px;
    background: rgba(157, 119, 225, 0.72);
  }

  &.register-page__blur--right {
    right: -120px;
    bottom: -80px;
    background: rgba(196, 169, 244, 0.7);
  }
}

.register-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(320px, 420px);
  gap: 24px;
  width: min(960px, 100%);
  align-items: stretch;
}

.register-brand,
.register-card {
  border-radius: 18px;
  backdrop-filter: blur(16px);
}

.register-brand {
  padding: 40px 36px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(112, 74, 198, 0.16);
  color: #3d3155;
  display: flex;
  flex-direction: column;
  justify-content: center;

  .register-brand__tag {
    width: fit-content;
    padding: 4px 12px;
    margin-bottom: 16px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: #ede9fe;
    background: rgba(124, 77, 200, 0.16);
  }

  h1 {
    margin: 0;
    font-size: 34px;
    line-height: 1.2;
    color: #241b35;
  }

  p {
    margin-top: 14px;
    margin-bottom: 0;
    color: #66577a;
    line-height: 1.7;
  }
}

.register-card {
  padding: 32px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(112, 74, 198, 0.16);
  box-shadow: 0 20px 40px rgba(77, 45, 135, 0.14);

  h2 {
    margin: 0;
    font-size: 26px;
    color: #241b35;
  }

  .register-card__hint {
    margin: 8px 0 24px;
    color: #766987;
    font-size: 14px;
  }
}

.register-form {
  :deep(.el-input__wrapper) {
    border-radius: 10px;
    box-shadow: 0 0 0 1px #e3d9f5 inset;
  }

  :deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 0 0 1px var(--el-color-primary) inset;
  }

  .submit-btn {
    width: 100%;
    margin-top: 4px;
    border-radius: 10px;
    font-weight: 600;
  }

  .form-footer {
    text-align: center;
    margin-top: 16px;

    a {
      color: #704ac6;
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}

@media (max-width: 900px) {
  .register-shell {
    grid-template-columns: 1fr;
  }

  .register-brand {
    padding: 28px;
  }
}

@media (max-width: 480px) {
  .register-page {
    padding: 16px;
  }

  .register-card {
    padding: 24px 18px;
  }

  .register-brand h1 {
    font-size: 28px;
  }
}
</style>
