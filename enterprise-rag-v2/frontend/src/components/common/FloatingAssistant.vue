<template>
  <div class="assistant-launcher">
    <button class="assistant-button" aria-label="打开 AI 助手" @click="openAssistant">
      <span class="assistant-spark">✦</span>
      <span class="assistant-label">AI 助手</span>
    </button>

    <el-drawer v-model="visible" title="AI 助手" direction="rtl" size="390px" destroy-on-close>
      <div class="assistant-panel">
        <div class="assistant-intro">
          <div class="intro-icon">✦</div>
          <div><strong>问问你的知识库</strong><p>在任何页面快速查找资料、总结结论或继续研究。</p></div>
        </div>

        <el-form label-position="top" class="assistant-form">
          <el-form-item label="知识库">
            <el-select v-model="datasetId" :loading="loadingDatasets" placeholder="选择一个知识库" style="width:100%">
              <el-option v-for="dataset in datasetStore.datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="问题">
            <el-input v-model="question" type="textarea" :rows="5" maxlength="1000" show-word-limit placeholder="例如：帮我总结最近导入资料里的三个关键结论" @keydown.enter.exact.prevent="submit" />
          </el-form-item>
        </el-form>

        <el-alert v-if="errorMessage" type="warning" :closable="false" show-icon class="assistant-alert">{{ errorMessage }}</el-alert>
        <div v-if="answer" class="assistant-answer">
          <div class="answer-heading"><span>回答</span><el-tag v-if="sourceCount" size="small" effect="plain">{{ sourceCount }} 条引用</el-tag></div>
          <p>{{ answer }}</p>
          <el-button link type="primary" @click="openFullChat">在完整问答中继续 <el-icon><ArrowRight /></el-icon></el-button>
        </div>
        <el-empty v-else-if="!submitting && !errorMessage" description="提交问题后，回答会显示在这里" :image-size="66" />

      </div>
      <template #footer>
        <div class="drawer-footer"><el-button @click="visible=false">关闭</el-button><el-button type="primary" :loading="submitting" :disabled="!datasetId || !question.trim()" @click="submit"><el-icon><Promotion /></el-icon>{{ submitting ? 'AI 思考中' : '发送问题' }}</el-button></div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Promotion } from '@element-plus/icons-vue'
import { useDatasetStore } from '@/stores/dataset'
import { submitAsyncChatJob, getAsyncChatJobStatus, getConversationMessages } from '@/api/chat'

const router = useRouter()
const datasetStore = useDatasetStore()
const visible = ref(false)
const loadingDatasets = ref(false)
const submitting = ref(false)
const datasetId = ref('')
const question = ref('')
const answer = ref('')
const sourceCount = ref(0)
const errorMessage = ref('')

const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

async function openAssistant() {
  visible.value = true
  errorMessage.value = ''
  if (datasetStore.datasets.length) {
    if (!datasetId.value) datasetId.value = datasetStore.datasets[0].id
    return
  }
  loadingDatasets.value = true
  try {
    await datasetStore.fetchDatasets({ silent: true })
    datasetId.value = datasetStore.datasets[0]?.id || ''
    if (!datasetId.value) errorMessage.value = '当前工作空间还没有知识库，请先导入资料。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '知识库加载失败，请稍后重试。'
  } finally { loadingDatasets.value = false }
}

async function submit() {
  if (!datasetId.value || !question.value.trim() || submitting.value) return
  submitting.value = true; errorMessage.value = ''; answer.value = ''; sourceCount.value = 0
  try {
    const submitted = await submitAsyncChatJob({ dataset_id: datasetId.value, query: question.value.trim() })
    const payload = submitted?.data || submitted
    const jobId = String(payload?.job_id || '')
    if (!jobId) throw new Error('未获取到问答任务 ID')
    for (let attempt = 0; attempt < 120; attempt += 1) {
      await sleep(1500)
      const statusResponse = await getAsyncChatJobStatus(jobId)
      const statusPayload = statusResponse?.data || statusResponse
      const status = String(statusPayload?.status || '').toUpperCase()
      if (status === 'SUCCESS') {
        const result = statusPayload?.result || {}
        const conversationId = String(result.conversation_id || '')
        if (conversationId) {
          const messagesResponse = await getConversationMessages(conversationId)
          const rawMessages = Array.isArray(messagesResponse) ? messagesResponse : (messagesResponse?.data || messagesResponse?.items || [])
          const latestAssistant = [...rawMessages].reverse().find((item: any) => item?.role === 'assistant')
          answer.value = String(latestAssistant?.content || result.answer || result.content || '任务已完成，但没有返回文字回答。')
          const sources = latestAssistant?.sources || latestAssistant?.retrieved_chunks || []
          sourceCount.value = Array.isArray(sources) ? sources.length : 0
        } else {
          answer.value = String(result.answer || result.content || '任务已完成，但没有返回文字回答。')
          sourceCount.value = Array.isArray(result.sources) ? result.sources.length : 0
        }
        return
      }
      if (status === 'FAILURE') throw new Error(String(statusPayload?.error || '问答任务执行失败'))
    }
    throw new Error('等待回答超时，请进入完整问答页查看')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '问答失败，请稍后重试。'
    ElMessage.warning(errorMessage.value)
  } finally { submitting.value = false }
}

function openFullChat() {
  visible.value = false
  router.push(`/chat/${datasetId.value}`)
}
</script>

<style scoped lang="scss">
.assistant-launcher { position:fixed; right:22px; bottom:26px; z-index:1200; }.assistant-button { display:flex; align-items:center; gap:8px; padding:10px 15px; color:#fff; cursor:pointer; border:1px solid rgba(255,255,255,.38); border-radius:999px; background:linear-gradient(135deg,#7950d8,#5c31b8); box-shadow:0 12px 28px rgba(91,49,184,.28); transition:.2s ease; }.assistant-button:hover { transform:translateY(-2px); box-shadow:0 16px 34px rgba(91,49,184,.38); }.assistant-spark { font-size:18px; line-height:1; }.assistant-label { font-size:13px; font-weight:700; }.assistant-panel { min-height:100%; }.assistant-intro { display:flex; gap:12px; padding:14px; border:1px solid rgba(112,74,198,.12); border-radius:15px; background:#faf7ff; }.intro-icon { display:grid; width:36px; height:36px; flex:0 0 36px; place-items:center; color:#fff; border-radius:12px; background:linear-gradient(135deg,#8c5be5,#6330c5); }.assistant-intro strong { color:#38254f; font-size:14px; }.assistant-intro p { margin:5px 0 0; color:#8c8297; font-size:12px; line-height:1.5; }.assistant-form { margin-top:20px; }.assistant-alert { margin-bottom:14px; }.assistant-answer { padding:15px; border:1px solid rgba(112,74,198,.14); border-radius:15px; background:#fbfaff; }.answer-heading { display:flex; align-items:center; justify-content:space-between; color:#5e3aa2; font-size:13px; font-weight:700; }.assistant-answer p { margin:12px 0 14px; color:#4f4459; white-space:pre-wrap; font-size:14px; line-height:1.75; }.drawer-footer { display:flex; justify-content:flex-end; gap:10px; padding-top:14px; border-top:1px solid rgba(112,74,198,.1); }@media(max-width:600px){.assistant-launcher{right:14px;bottom:16px}.assistant-button{padding:10px 13px}.assistant-label{display:none}.assistant-spark{font-size:20px}}
</style>
