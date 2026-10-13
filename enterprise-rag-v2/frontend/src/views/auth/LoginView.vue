<template>
  <div class="login-page">
    <div class="login-page__blur login-page__blur--left" />
    <div class="login-page__blur login-page__blur--right" />

    <div class="login-shell">
      <section class="login-brand">
        <h1 class="login-brand__title">
          知域引擎
        </h1>
        <p class="login-brand__slogan">
          把散落的信息变成可搜索的知识库 — 微信聊天、截图、文档，拖进来就能搜。
        </p>
      </section>

      <section class="login-card">
        <h2>账号登录</h2>
        <p class="login-card__hint">
          请输入邮箱和密码继续使用
        </p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="login-form"
          @submit.prevent="handleLogin"
        >
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
              placeholder="请输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="authStore.loading"
              class="submit-btn"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <router-link to="/register">
              还没有账号？立即注册
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
import { Message, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { validateEmail, validatePasswordStrength } from '@/utils/validate'
import type { FormInstance } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()

const form = reactive({
  email: '',
  password: ''
})

const rules = {
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
      const result = validatePasswordStrength(value)
      if (!result.valid) {
        callback(new Error(result.message))
      } else {
        callback()
      }
    }, trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        await authStore.loginUser(form)
        router.push('/')
      } catch (e: any) {
        const detail = e.response?.data?.detail
        if (detail) {
          if (detail.includes('不存在')) {
            ElMessage.error('该账号不存在，请联系管理员注册')
          } else if (detail.includes('密码')) {
            ElMessage.error('密码错误，请重试')
          } else if (detail.includes('锁定')) {
            ElMessage.warning('该账号已被锁定，请稍后重试或联系管理员')
          } else if (detail.includes('禁用')) {
            ElMessage.warning('该账号已被禁用，请联系管理员')
          } else {
            ElMessage.error(detail)
          }
        } else if (e.message?.includes('Network Error')) {
          ElMessage.error('网络连接失败，请检查网络后重试')
        } else if (e.code === 'ECONNABORTED' || e.message?.includes('timeout')) {
          ElMessage.error('请求超时，请检查网络后重试')
        } else {
          ElMessage.error('登录失败，请检查账号和密码后重试')
        }
      }
    }
  })
}
</script>

<style scoped lang="scss">
.login-page {
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

.login-page__blur {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.45;
  pointer-events: none;

  &.login-page__blur--left {
    top: -70px;
    left: -100px;
    background: rgba(157, 119, 225, 0.72);
  }

  &.login-page__blur--right {
    right: -120px;
    bottom: -80px;
    background: rgba(196, 169, 244, 0.7);
  }
}

.login-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(320px, 420px);
  gap: 24px;
  width: min(960px, 100%);
  align-items: stretch;
}

.login-brand,
.login-card {
  border-radius: 18px;
  backdrop-filter: blur(16px);
}

.login-brand {
  padding: 40px 36px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(112, 74, 198, 0.16);
  color: #3d3155;
  display: flex;
  flex-direction: column;
  justify-content: center;

  .login-brand__title {
    margin: 0;
    font-size: 36px;
    font-weight: 800;
    letter-spacing: 0.04em;
    line-height: 1.15;
    color: #241b35;
  }

  .login-brand__slogan {
    margin: 14px 0 0;
    font-size: 15px;
    line-height: 1.75;
    color: #66577a;
  }


}

.login-card {
  padding: 32px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(112, 74, 198, 0.16);
  box-shadow: 0 20px 40px rgba(77, 45, 135, 0.14);

  h2 {
    margin: 0;
    font-size: 26px;
    color: #241b35;
  }

  .login-card__hint {
    margin: 8px 0 24px;
    color: #766987;
    font-size: 14px;
  }
}

.login-form {
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
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-brand {
    padding: 28px;
  }
}

@media (max-width: 480px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    padding: 24px 18px;
  }

  .login-brand__title {
    font-size: 30px;
  }


}
</style>
