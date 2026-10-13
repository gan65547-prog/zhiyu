<template>
  <div class="settings-view">
    <div class="page-intro">
      <span class="section-kicker">WORKSPACE PREFERENCES</span>
      <h1>系统设置</h1>
      <p>管理你的工作台偏好、模型运行方式与安全选项。</p>
    </div>
    <el-card class="settings-card">
      <el-tabs
        v-model="activeTab"
        class="settings-tabs"
      >
        <el-tab-pane
          label="系统设置"
          name="system"
        >
          <div class="tab-content">
            <el-alert
              title="提示"
              type="info"
              :closable="false"
              style="margin-bottom: 20px;"
            >
              <template #default>
                系统偏好会保存到服务端，并同步到当前浏览器；模型提供商、API密钥等部署级配置仍由管理员维护。
              </template>
            </el-alert>
            
            <el-form
              :model="systemForm"
              label-width="140px"
            >
              <el-form-item label="主题模式">
                <el-radio-group v-model="systemForm.theme">
                  <el-radio value="light">
                    浅色模式
                  </el-radio>
                  <el-radio value="dark">
                    深色模式
                  </el-radio>
                  <el-radio value="auto">
                    跟随系统
                  </el-radio>
                </el-radio-group>
              </el-form-item>

              <el-form-item label="语言">
                <el-select
                  v-model="systemForm.language"
                  placeholder="请选择语言"
                >
                  <el-option
                    label="简体中文"
                    value="zh-CN"
                  />
                  <el-option
                    label="English"
                    value="en-US"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="默认页面">
                <el-select
                  v-model="systemForm.defaultPage"
                  placeholder="请选择默认页面"
                >
                  <el-option
                    label="首页"
                    value="/"
                  />
                  <el-option
                    label="知识库"
                    value="/datasets"
                  />
                  <el-option
                    label="智能问答"
                    value="/chat"
                  />
                </el-select>
              </el-form-item>

              <el-form-item>
                <el-button
                  type="primary"
                  @click="saveSystemSettings"
                >
                  保存设置
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="模型配置"
          name="model"
        >
          <div class="tab-content">
            <el-alert
              title="提示"
              type="info"
              :closable="false"
              style="margin-bottom: 20px;"
            >
              <template #default>
                这些是当前用户的检索偏好，已保存到服务端；系统级模型提供商和环境变量仍由部署管理员维护。
              </template>
            </el-alert>
            <div class="model-health-card">
              <div>
                <span class="health-kicker">RUNTIME HEALTH</span>
                <strong>模型运行状态</strong>
                <small>{{ modelHealthMessage }}</small>
              </div>
              <div class="health-actions">
                <el-tag :type="modelHealthTag" effect="plain">{{ modelHealthLabel }}</el-tag>
                <el-button text type="primary" :loading="modelHealthLoading" @click="loadModelHealth">重新探测</el-button>
              </div>
            </div>
            
            <el-form
              :model="modelForm"
              label-width="140px"
            >
              <el-form-item label="Embedding模型">
                <el-select
                  v-model="modelForm.embeddingModel"
                  placeholder="请选择Embedding模型"
                >
                  <el-option
                    label="bge-small-zh-v1.5 (当前)"
                    value="bge-small-zh-v1.5"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="LLM模型">
                <el-select
                  v-model="modelForm.llmModel"
                  placeholder="请选择LLM模型"
                >
                  <el-option
                    label="deepseek-chat (当前)"
                    value="deepseek-chat"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="温度参数">
                <el-slider
                  v-model="modelForm.temperature"
                  :min="0"
                  :max="1"
                  :step="0.1"
                  show-input
                />
              </el-form-item>

              <el-form-item label="Top K">
                <el-input-number
                  v-model="modelForm.topK"
                  :min="1"
                  :max="20"
                />
                <div class="form-tip">
                  设置检索返回的文档块数量
                </div>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="savingConfig" @click="saveModelSettings">
                  保存模型偏好
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="API密钥"
          name="api"
        >
          <div class="tab-content">
            <el-alert
              title="提示"
              type="info"
              :closable="false"
              style="margin-bottom: 20px;"
            >
              <template #default>
                API Key 会加密保存，页面只显示名称和配置状态，不会回显明文。请仅保存只读或最小权限密钥。
              </template>
            </el-alert>
            <div class="api-key-list">
              <el-empty v-if="!apiKeys.length" description="还没有保存 API Key" />
              <div v-for="item in apiKeys" :key="item.id" class="api-key-item">
                <div>
                  <strong>{{ item.name }}</strong>
                  <span class="form-tip">{{ item.provider }} · {{ item.base_url || '默认 Base URL' }}</span>
                </div>
                <div class="api-key-actions">
                  <el-tag type="success" effect="plain">已加密配置</el-tag>
                  <el-tag v-if="item.is_default" effect="plain">默认</el-tag>
                  <el-button link type="danger" @click="removeApiKey(item.id, item.name)">删除</el-button>
                </div>
              </div>
            </div>
            <el-divider />
            <el-form :model="apiForm" label-width="140px">
              <el-form-item label="Provider">
                <el-input v-model="apiForm.provider" autocomplete="off" placeholder="例如 openai、deepseek" />
              </el-form-item>
              <el-form-item label="名称">
                <el-input v-model="apiForm.name" autocomplete="off" placeholder="例如 工作台默认模型" />
              </el-form-item>
              <el-form-item label="API Key">
                <el-input v-model="apiForm.apiKey" type="password" autocomplete="new-password" placeholder="只在保存时提交，不会回显" show-password />
              </el-form-item>
              <el-form-item label="API Base URL">
                <el-input v-model="apiForm.baseUrl" placeholder="可选，例如 https://api.deepseek.com/v1" />
              </el-form-item>
              <el-form-item label="设为默认">
                <el-switch v-model="apiForm.isDefault" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="savingApiKey" @click="saveApiKey">保存 API Key</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="安全设置"
          name="security"
        >
          <div class="tab-content">
            <el-alert
              title="提示"
              type="warning"
              :closable="false"
              style="margin-bottom: 20px;"
            >
              <template #default>
                会话时长和两步验证偏好已支持服务端保存；真正启用 2FA 和 IP 白名单前，还需要接入组织级安全策略。
              </template>
            </el-alert>
            
            <el-form
              :model="securityForm"
              label-width="140px"
            >
              <el-form-item label="登录会话超时">
                <el-select
                  v-model="securityForm.sessionTimeout"
                  placeholder="请选择会话时长"
                >
                  <el-option
                    label="30分钟"
                    :value="30"
                  />
                  <el-option
                    label="2小时"
                    :value="120"
                  />
                  <el-option
                    label="1天"
                    :value="1440"
                  />
                  <el-option
                    label="7天"
                    :value="10080"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="两步验证">
                <el-switch
                  v-model="securityForm.twoFactorAuth"
                />
                <div class="form-tip">
                  当前仅保存偏好，启用策略需要管理员确认
                </div>
              </el-form-item>

              <el-form-item label="登录IP白名单">
                <el-input
                  v-model="securityForm.ipWhitelist"
                  type="textarea"
                  :rows="3"
                  placeholder="每行或用逗号分隔一个IP或CIDR"
                />
                <div class="form-tip">
                  当前仅保存偏好；真正拦截登录需要部署层接入安全策略
                </div>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" :loading="savingConfig" @click="saveSecuritySettings">
                  保存安全偏好
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserConfigStore } from '@/stores/userConfig'
import { userConfigApi, type UserConfigPayload } from '@/api/userConfig'
import { userApiKeysApi, type UserApiKey } from '@/api/userApiKeys'
import request from '@/api/request'

const activeTab = ref('system')
const userConfigStore = useUserConfigStore()
const savingConfig = ref(false)
const savingApiKey = ref(false)
const apiKeys = ref<UserApiKey[]>([])
const modelHealthLoading = ref(false)
const modelHealth = ref<{ status: string; message?: string; provider?: string; model?: string } | null>(null)

const systemForm = reactive({
  theme: 'light' as 'light' | 'dark' | 'auto',
  language: 'zh-CN' as 'zh-CN' | 'en-US',
  defaultPage: '/'
})

const modelForm = reactive({
  embeddingModel: 'bge-small-zh-v1.5',
  llmModel: 'deepseek-chat',
  temperature: 0.7,
  topK: 5
})

const apiForm = reactive({
  provider: 'deepseek',
  name: '',
  apiKey: '',
  baseUrl: '',
  isDefault: true
})

const securityForm = reactive({
  sessionTimeout: 1440,
  twoFactorAuth: false,
  ipWhitelist: ''
})

onMounted(() => {
  // 从 store 加载配置到表单
  if (userConfigStore.isLoaded) {
    syncFormFromStore()
  } else {
    // 等待 store 加载
    const unwatch = watch(() => userConfigStore.isLoaded, (loaded) => {
      if (loaded) {
        syncFormFromStore()
        unwatch()
      }
    })
  }
  void loadServerConfig()
  void loadApiKeys()
  void loadModelHealth()
})

const syncFormFromStore = () => {
  Object.assign(systemForm, userConfigStore.config)
}

const applyServerConfig = (config: UserConfigPayload) => {
  Object.assign(systemForm, {
    theme: config.theme,
    language: config.language,
    defaultPage: config.defaultPage
  })
  Object.assign(modelForm, {
    embeddingModel: config.embeddingModel,
    llmModel: config.llmModel,
    temperature: config.temperature,
    topK: config.topK
  })
  Object.assign(securityForm, {
    sessionTimeout: config.sessionTimeout,
    twoFactorAuth: config.twoFactorAuth,
    ipWhitelist: config.ipWhitelist
  })
  userConfigStore.updateConfig({
    theme: config.theme,
    language: config.language,
    defaultPage: config.defaultPage
  })
}

const toPayload = (): UserConfigPayload => ({
  theme: systemForm.theme,
  language: systemForm.language,
  defaultPage: systemForm.defaultPage,
  embeddingModel: modelForm.embeddingModel,
  llmModel: modelForm.llmModel,
  temperature: modelForm.temperature,
  topK: modelForm.topK,
  sessionTimeout: securityForm.sessionTimeout,
  twoFactorAuth: securityForm.twoFactorAuth,
  ipWhitelist: securityForm.ipWhitelist
})

const loadServerConfig = async () => {
  try {
    applyServerConfig(await userConfigApi.get())
  } catch (error) {
    // 未迁移的旧部署仍可继续使用本地配置，不阻塞设置页。
    console.warn('服务端配置读取失败，继续使用本地配置', error)
  }
}

const saveSystemSettings = () => saveConfig('系统设置已保存')

const saveConfig = async (successMessage: string) => {
  savingConfig.value = true
  try {
    const saved = await userConfigApi.update(toPayload())
    applyServerConfig(saved)
    ElMessage.success(successMessage)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '设置保存失败，请稍后重试')
  } finally {
    savingConfig.value = false
  }
}

const saveModelSettings = () => saveConfig('模型偏好已保存')
const saveSecuritySettings = () => saveConfig('安全偏好已保存')

const loadApiKeys = async () => {
  try {
    apiKeys.value = await userApiKeysApi.list()
  } catch {
    // 兼容尚未升级的旧后端，不把配置页变成错误页。
    apiKeys.value = []
  }
}

const loadModelHealth = async () => {
  modelHealthLoading.value = true
  try {
    const response = await request.get<{ status: string; components?: Array<{ name: string; status: string; message?: string; details?: { provider?: string; model?: string } }> }>('/health')
    const component = response.components?.find((item: { name: string; status: string; message?: string; details?: { provider?: string; model?: string } }) => item.name === 'llm')
    modelHealth.value = component
      ? { status: component.status, message: component.message, provider: component.details?.provider, model: component.details?.model }
      : { status: response.status, message: '未返回模型组件状态' }
  } catch (error) {
    modelHealth.value = { status: 'unhealthy', message: error instanceof Error ? error.message : '健康检查失败' }
  } finally {
    modelHealthLoading.value = false
  }
}

const modelHealthLabel = computed(() => ({ healthy: '可用', degraded: '降级', unhealthy: '不可用' }[modelHealth.value?.status || ''] || '未探测'))
const modelHealthTag = computed(() => modelHealth.value?.status === 'healthy' ? 'success' : modelHealth.value?.status === 'unhealthy' ? 'danger' : 'warning')
const modelHealthMessage = computed(() => {
  const value = modelHealth.value
  if (!value) return '正在读取当前运行时 provider 和可达性。'
  return [value.provider, value.model, value.message || '当前 provider 可正常响应'].filter(Boolean).join(' · ')
})

const saveApiKey = async () => {
  if (!apiForm.provider.trim() || !apiForm.name.trim() || !apiForm.apiKey.trim()) {
    ElMessage.warning('请填写 Provider、名称和 API Key')
    return
  }
  savingApiKey.value = true
  try {
    await userApiKeysApi.create({
      provider: apiForm.provider.trim(),
      name: apiForm.name.trim(),
      api_key: apiForm.apiKey.trim(),
      base_url: apiForm.baseUrl.trim() || undefined,
      is_default: apiForm.isDefault
    })
    apiForm.apiKey = ''
    apiForm.name = ''
    apiForm.baseUrl = ''
    ElMessage.success('API Key 已加密保存')
    await loadApiKeys()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'API Key 保存失败，请确认服务端已配置加密密钥')
  } finally {
    savingApiKey.value = false
  }
}

const removeApiKey = async (id: string, name: string) => {
  await ElMessageBox.confirm(`确认删除“${name}”吗？删除后不会再用于模型调用。`, '删除 API Key', { type: 'warning' })
  try {
    await userApiKeysApi.remove(id)
    ElMessage.success('API Key 已删除')
    await loadApiKeys()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'API Key 删除失败')
  }
}
</script>

<style scoped lang="scss">
.settings-view {
  max-width: 900px;

  .page-intro {
    margin-bottom: 22px;

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

  .settings-card {
    :deep(.el-tabs__content) {
      padding-top: 20px;
    }
  }

  .model-health-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 22px;
    padding: 14px 16px;
    border: 1px solid rgba(112, 74, 198, .14);
    border-radius: 14px;
    background: linear-gradient(145deg, #faf8ff, #fff);

    > div:first-child {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .health-kicker {
      color: var(--el-color-primary);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .14em;
    }

    strong { color: #322442; }
    small { color: var(--el-text-color-secondary); line-height: 1.5; }
    .health-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  }

  .tab-content {
    max-width: 600px;

    .form-tip {
      font-size: 12px;
      color: #827a90;
      margin-top: 4px;
    }

    .api-key-list {
      display: grid;
      gap: 10px;

      .api-key-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 14px 16px;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        background: var(--surface-soft);
      }

      .api-key-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }
    }
  }

  @media (max-width: 680px) {
    .settings-card {
      :deep(.el-tabs__nav-wrap) {
        overflow-x: auto;
      }

      :deep(.el-tabs__nav) {
        min-width: max-content;
      }
    }

    .model-health-card {
      align-items: flex-start;
      flex-direction: column;

      .health-actions {
        width: 100%;
        justify-content: space-between;
      }
    }

    .tab-content :deep(.el-form-item) {
      display: block;
      margin-bottom: 18px;

      .el-form-item__label {
        display: block;
        width: auto !important;
        padding: 0 0 7px;
        line-height: 1.4;
        text-align: left;
      }

      .el-form-item__content {
        margin-left: 0 !important;
      }
    }

    .api-key-item {
      align-items: flex-start !important;
      flex-direction: column;

      .api-key-actions {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
      }
    }
  }
}
</style>
