<template>
  <div class="wechat-import-view">
    <div class="header">
      <div class="header-left">
        <el-button text @click="router.push(`/datasets/${datasetId}`)">
          <el-icon><ArrowLeft /></el-icon>
          返回知识库
        </el-button>
        <h1>导入微信聊天记录</h1>
      </div>
    </div>

    <el-row :gutter="24">
      <el-col :span="16">
        <el-card class="upload-card">
          <template #header>
            <span>选择聊天记录文件</span>
          </template>

          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            accept=".txt,.csv"
            :limit="1"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              <span>将微信聊天记录文件拖到此处，或</span>
              <em>点击选择文件</em>
            </div>
            <template #tip>
              <div class="upload-tip">
                支持 .txt / .csv 格式的聊天记录导出文件
              </div>
            </template>
          </el-upload>

          <el-form
            v-if="selectedFile"
            class="import-form"
            label-width="100px"
          >
            <el-form-item label="聊天名称">
              <el-input
                v-model="chatName"
                placeholder="例如：与张三的聊天记录（可选，用于搜索时识别）"
                clearable
              />
              <div class="form-item-tip">
                留空则自动使用文件名
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="importing"
                @click="handleImport"
              >
                <el-icon><Upload /></el-icon>
                开始导入
              </el-button>
              <el-button @click="handleClear">
                取消
              </el-button>
            </el-form-item>
          </el-form>

          <div
            v-if="importResult"
            class="import-result"
          >
            <el-alert
              :title="`成功导入 ${importResult.total_messages} 条聊天记录`"
              type="success"
              :closable="false"
              show-icon
            >
              <template #default>
                <div class="result-detail">
                  <p v-if="importResult.participants?.length">
                    参与人：{{ importResult.participants.join('、') }}
                  </p>
                  <p v-if="importResult.date_range?.length === 2">
                    时间范围：{{ importResult.date_range[0] }} ~ {{ importResult.date_range[1] }}
                  </p>
                  <p>文件格式：{{ importResult.format_detected?.toUpperCase() }}</p>
                </div>
                <div class="result-actions">
                  <el-button
                    type="primary"
                    @click="router.push(`/chat/${datasetId}`)"
                  >
                    <el-icon><ChatDotRound /></el-icon>
                    去搜索提问
                  </el-button>
                  <el-button @click="router.push(`/datasets/${datasetId}`)">
                    <el-icon><Document /></el-icon>
                    查看文档列表
                  </el-button>
                </div>
              </template>
            </el-alert>
          </div>

          <div
            v-if="importError"
            class="import-error"
          >
            <el-alert
              :title="importError"
              type="error"
              show-icon
              @close="importError = ''"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="guide-card">
          <template #header>
            <span>如何导出微信聊天记录？</span>
          </template>

          <div class="guide-steps">
            <div class="step">
              <div class="step-number">1</div>
              <div class="step-content">
                <strong>下载 WeChatMsg 工具</strong>
                <p>从 GitHub 搜索 <code>LC044/WeChatMsg</code> 下载最新版本</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">2</div>
              <div class="step-content">
                <strong>导出聊天记录</strong>
                <p>打开 WeChatMsg → 选择聊天 → 导出为 <code>TXT</code> 格式</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">3</div>
              <div class="step-content">
                <strong>上传到知域引擎</strong>
                <p>将导出的 .txt 文件拖到左侧上传区域</p>
              </div>
            </div>

            <div class="step">
              <div class="step-number">4</div>
              <div class="step-content">
                <strong>AI 对话搜索</strong>
                <p>导入完成后，去问答页面直接提问聊天内容</p>
              </div>
            </div>
          </div>

          <el-divider />

          <div class="privacy-note">
            <el-icon><Lock /></el-icon>
            <span>你的聊天记录保存在你自己的服务器上，不会上传到第三方</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, UploadFilled, Upload, ChatDotRound, Document, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { importWechatChat } from '@/api/document'

const router = useRouter()
const route = useRoute()

const datasetId = computed(() => route.params.id as string)

const uploadRef = ref()
const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const chatName = ref('')
const importing = ref(false)
const importResult = ref<any>(null)
const importError = ref('')

function handleFileChange(file: any) {
  fileList.value = [file]
  selectedFile.value = file.raw
  importError.value = ''
  importResult.value = null
}

function handleClear() {
  fileList.value = []
  selectedFile.value = null
  chatName.value = ''
  importError.value = ''
  importResult.value = null
}

async function handleImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择聊天记录文件')
    return
  }

  importing.value = true
  importError.value = ''
  importResult.value = null

  try {
    const res = await importWechatChat(
      datasetId.value,
      selectedFile.value,
      chatName.value || undefined
    )

    if (res.data) {
      importResult.value = res.data
      ElMessage.success(`成功导入 ${res.data.total_messages} 条聊天记录`)
    }
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message || '导入失败'
    importError.value = typeof detail === 'string' ? detail : JSON.stringify(detail)
    ElMessage.error(importError.value)
  } finally {
    importing.value = false
  }
}
</script>

<style scoped lang="scss">
.wechat-import-view {
  padding-bottom: 32px;
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      h1 {
        margin: 0;
        font-size: 30px;
        font-weight: 760;
        letter-spacing: -0.04em;
        color: #241d2e;
      }
    }
  }
}

.upload-card {
  border: 1px solid rgba(124, 77, 200, 0.14);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(62, 42, 108, 0.07);
  :deep(.el-upload-dragger) {
    padding: 40px 20px;
    border-color: rgba(124, 77, 200, 0.28);
    background: rgba(124, 77, 200, 0.035);
  }
}

.upload-icon {
  font-size: 48px;
  color: var(--el-color-primary);
  margin-bottom: 12px;
}

.upload-text {
  font-size: 15px;
  color: var(--el-text-color-regular);

  em {
    color: var(--el-color-primary);
    font-style: normal;
  }
}

.upload-tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-top: 8px;
}

.import-form {
  margin-top: 24px;

  .form-item-tip {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-top: 4px;
  }
}

.import-result {
  margin-top: 24px;

  .result-detail {
    margin: 12px 0;

    p {
      margin: 4px 0;
      font-size: 14px;
    }
  }

  .result-actions {
    margin-top: 16px;
    display: flex;
    gap: 12px;
  }
}

.import-error {
  margin-top: 20px;
}

.guide-card {
  border: 1px solid rgba(124, 77, 200, 0.14);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(62, 42, 108, 0.07);
  .guide-steps {
    .step {
      display: flex;
      gap: 14px;
      margin-bottom: 20px;

      &:last-child {
        margin-bottom: 0;
      }

      .step-number {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: linear-gradient(145deg, #8d5cf6, #5b32bd);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
        flex-shrink: 0;
      }

      .step-content {
        strong {
          display: block;
          font-size: 14px;
          color: var(--el-text-color-primary);
          margin-bottom: 4px;
        }

        p {
          margin: 0;
          font-size: 13px;
          color: var(--el-text-color-secondary);
          line-height: 1.6;
        }

        code {
          background: var(--el-fill-color);
          padding: 1px 6px;
          border-radius: 4px;
          font-size: 12px;
        }
      }
    }
  }
}

.privacy-note {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;

  .el-icon {
    color: var(--el-color-success);
    flex-shrink: 0;
  }
}
</style>
