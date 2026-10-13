<template>
  <div class="diagnosis-page">
    <!-- ============================================================
         View: Diagnosis Form + SSE Report  (/learning)
         ============================================================ -->
    <template v-if="route.name === 'LearningDiagnosis'">
      <!-- Left Panel: Input Form -->
      <div class="input-panel">
        <div class="panel-header">
          <h2>学习诊断</h2>
          <el-button size="small" text @click="router.push('/learning/history')">历史报告</el-button>
        </div>

        <div class="panel-body">
          <el-form label-position="top" size="default">
            <el-form-item label="学科">
              <el-select v-model="subjectId" filterable clearable placeholder="选择学科">
                <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="年级">
              <el-select v-model="gradeLevel" placeholder="选择年级">
                <el-option v-for="g in [7, 8, 9]" :key="g" :label="`${g}年级`" :value="g" />
              </el-select>
            </el-form-item>

            <el-form-item label="题目/错题描述" required>
              <el-input
                v-model="questionText"
                type="textarea"
                :rows="5"
                placeholder="请描述你做错的题目，或直接粘贴题目内容&#10;&#10;例如：解方程 3x+5=2x-1，我移项时总是忘记变号"
              />
            </el-form-item>

            <el-form-item label="你的答案（可选）">
              <el-input v-model="originalAnswer" type="textarea" :rows="2" placeholder="可以粘贴你写的过程或答案" />
            </el-form-item>

            <el-form-item label="错误类型（可选）">
              <div class="symptom-tags">
                <el-tag
                  v-for="tag in errorTagOptions" :key="tag"
                  :type="selectedErrorTags.includes(tag) ? 'primary' : 'info'"
                  :effect="selectedErrorTags.includes(tag) ? 'dark' : 'plain'"
                  class="symptom-tag" @click="toggleErrorTag(tag)"
                >{{ tag }}</el-tag>
              </div>
            </el-form-item>

            <el-button type="primary" :loading="running" :disabled="!questionText.trim()" class="diagnose-btn" @click="startDiagnosis">
              {{ running ? '诊断中...' : '开始诊断' }}
            </el-button>
            <p class="hint">预计 10-20 秒</p>
          </el-form>
        </div>
      </div>

      <!-- Right Panel: Report -->
      <div class="report-panel">
        <div v-if="!started" class="empty-state">
          <div class="empty-icon">🎓</div>
          <h3>AI 学习诊断引擎</h3>
          <p>输入错题信息，AI 自动完成<br/>知识点定位 → 教材检索 → 错例分析 → 诊断报告</p>
        </div>

        <div v-else class="report-content">
          <div class="stage-bar">
            <div v-for="(s, i) in stages" :key="i" class="stage-item" :class="{ active: s.status === 'running', done: s.status === 'done' }">
              <span class="stage-dot"></span>
              <span class="stage-label">{{ s.name }}</span>
            </div>
          </div>
          <el-progress :percentage="Math.round(progress * 100)" :stroke-width="2" :show-text="false" class="stage-progress" />

          <el-alert v-if="diagnosisError" type="error" :closable="false" show-icon class="diagnosis-error">
            {{ diagnosisError }}
          </el-alert>

          <div v-for="(section, idx) in reportSections" :key="idx" class="report-card" :class="{ stream: section.streaming }">
            <h4 v-if="section.title">{{ section.title }}</h4>
            <div class="card-body" v-html="renderMarkdown(section.content)"></div>
            <span v-if="section.streaming" class="typing-cursor">|</span>
          </div>

          <div v-if="sources.length > 0" class="sources-card">
            <h4>参考来源</h4>
            <div v-for="(src, i) in sources" :key="i" class="source-item">
              <span class="source-title">{{ src.title || '教材素材' }}</span>
              <span class="source-text">{{ src.content?.slice(0, 200) }}...</span>
            </div>
          </div>

          <div v-if="diagnosisDone && !diagnosisError" class="action-bar">
            <el-button type="primary" @click="startPractice">靶向练习</el-button>
            <el-button type="primary" plain @click="copyReport">复制报告</el-button>
            <el-button @click="rateReport('useful')">👍 有用</el-button>
            <el-button @click="rateReport('useless')">👎 没用</el-button>
            <el-button @click="router.push('/learning/history')">历史报告</el-button>
          </div>
        </div>
      </div>
    </template>

    <!-- ============================================================
         View: History List  (/learning/history)
         ============================================================ -->
    <template v-else-if="route.name === 'LearningHistory'">
      <div class="history-page">
        <div class="page-header">
          <h2>诊断历史</h2>
          <el-button type="primary" @click="router.push('/learning')">新建诊断</el-button>
        </div>

        <el-table :data="historyList" stripe v-loading="historyLoading" empty-text="暂无诊断记录">
          <el-table-column prop="question_text" label="错题描述" min-width="260" show-overflow-tooltip />
          <el-table-column prop="grade_level" label="年级" width="70" />
          <el-table-column label="诊断时间" width="170">
            <template #default="{ row }">
              {{ new Date(row.created_at).toLocaleString('zh-CN') }}
            </template>
          </el-table-column>
          <el-table-column label="掌握度" width="120">
            <template #default="{ row }">
              <el-progress :percentage="row.overall_mastery_score || 0" :stroke-width="4" :show-text="true" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="router.push(`/learning/report/${row.id}`)">查看报告</el-button>
              <el-button size="small" text type="primary" @click="router.push(`/learning/practice/${row.id}`)">靶向练习</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap" v-if="historyTotal > historyPageSize">
          <el-pagination
            v-model:current-page="historyPage"
            :page-size="historyPageSize"
            :total="historyTotal"
            layout="prev, pager, next"
            @current-change="loadHistory"
          />
        </div>
      </div>
    </template>

    <!-- ============================================================
         View: Report Detail  (/learning/report/:id)
         ============================================================ -->
    <template v-else-if="route.name === 'LearningReport'">
      <div class="report-detail-page">
        <div class="page-header">
          <el-button text @click="router.push('/learning/history')">← 返回历史</el-button>
          <h2>诊断报告</h2>
        </div>

        <div v-loading="reportLoading" class="report-detail-body">
          <template v-if="reportDetail">
            <div class="report-meta">
              <el-tag>{{ reportDetail.grade_level }}年级</el-tag>
              <span class="meta-time">{{ new Date(reportDetail.created_at).toLocaleString('zh-CN') }}</span>
            </div>
            <div class="report-card">
              <h4>错题描述</h4>
              <p>{{ reportDetail.question_text }}</p>
            </div>
            <div v-if="reportDetail.report_content" class="report-card">
              <h4>诊断报告</h4>
              <div class="card-body" v-html="renderMarkdown(reportDetail.report_content.report_text || '')"></div>
            </div>
            <div v-if="reportDetail.weak_knowledge_points?.length" class="report-card">
              <h4>薄弱知识点</h4>
              <el-tag v-for="kp in reportDetail.weak_knowledge_points" :key="kp.kp_id" type="warning" style="margin: 4px">
                {{ kp.name }}
              </el-tag>
            </div>
            <div class="action-bar">
              <el-button type="primary" @click="router.push(`/learning/practice/${reportDetail.id}`)">靶向练习</el-button>
              <el-button @click="router.push('/learning')">新建诊断</el-button>
            </div>
          </template>
        </div>
      </div>
    </template>

    <!-- ============================================================
         View: Practice Session  (/learning/practice/:id)
         ============================================================ -->
    <template v-else-if="route.name === 'LearningPractice'">
      <div class="practice-page">
        <div class="page-header">
          <el-button text @click="router.back()">← 返回</el-button>
          <h2>靶向练习</h2>
        </div>

        <div v-loading="practiceLoading" class="practice-body">
          <div v-if="practiceSession" class="practice-content">
            <div class="practice-info">
              <el-tag :type="practiceSession.status === 'completed' ? 'success' : 'warning'">
                {{ practiceSession.status === 'completed' ? '已完成' : practiceSession.status === 'in_progress' ? '进行中' : '待开始' }}
              </el-tag>
              <span v-if="practiceSession.exercises_completed > 0" style="margin-left: 12px; color: #6b7280">
                完成 {{ practiceSession.exercises_completed }} / {{ practiceSession.exercises?.length || 0 }} 题，正确 {{ practiceSession.exercises_correct }} 题
              </span>
            </div>
            <div v-if="practiceSession.exercises?.length" class="exercise-list">
              <div v-for="(ex, i) in practiceSession.exercises" :key="i" class="exercise-card">
                <div class="exercise-header">
                  <h4>第 {{ ex.idx || i + 1 }} 题
                    <el-tag size="small" :type="ex.difficulty === 'hard' ? 'danger' : ex.difficulty === 'medium' ? 'warning' : 'success'" style="margin-left: 8px">
                      {{ ex.difficulty === 'hard' ? '困难' : ex.difficulty === 'medium' ? '中等' : '基础' }}
                    </el-tag>
                    <el-tag v-if="ex.kp_name" size="small" type="info" style="margin-left: 4px">{{ ex.kp_name }}</el-tag>
                    <el-tag v-if="practiceAnswerStates[ex.idx]?.submitted" size="small" :type="practiceAnswerStates[ex.idx]?.correct ? 'success' : 'danger'" style="margin-left: 4px">
                      {{ practiceAnswerStates[ex.idx]?.correct ? '✓ 正确' : '✗ 错误' }}
                    </el-tag>
                  </h4>
                </div>
                <p class="question-text">{{ ex.question }}</p>
                <div v-if="ex.hints?.length" class="hints">
                  <p style="font-size: 13px; color: #6b7280; margin-bottom: 4px">提示：</p>
                  <el-tag v-for="(h, hi) in ex.hints" :key="hi" size="small" type="info" effect="plain" style="margin-right: 4px; margin-bottom: 4px">{{ h }}</el-tag>
                </div>

                <!-- Answer input -->
                <div v-if="!practiceAnswerStates[ex.idx]?.submitted" class="answer-input">
                  <el-input
                    v-model="practiceAnswerStates[ex.idx].answer"
                    type="textarea"
                    :rows="3"
                    placeholder="输入你的答案..."
                    style="margin-top: 12px"
                  />
                  <el-button
                    type="primary"
                    size="small"
                    :loading="practiceAnswerStates[ex.idx]?.submitting"
                    :disabled="!practiceAnswerStates[ex.idx]?.answer?.trim()"
                    @click="submitAnswer(ex.idx)"
                    style="margin-top: 8px"
                  >
                    提交答案
                  </el-button>
                </div>

                <!-- Submitted feedback -->
                <div v-else class="answer-feedback" :class="{ correct: practiceAnswerStates[ex.idx]?.correct }">
                  <p><strong>{{ practiceAnswerStates[ex.idx]?.correct ? '✓ 回答正确！' : '✗ 回答有误' }}</strong></p>
                  <p v-if="!practiceAnswerStates[ex.idx]?.correct" style="color: #6b7280; font-size: 13px">
                    正确答案：{{ ex.answer?.substring(0, 200) }}{{ ex.answer?.length > 200 ? '...' : '' }}
                  </p>
                  <p style="color: #10b981; font-size: 13px">{{ practiceAnswerStates[ex.idx]?.encouragement }}</p>
                </div>
              </div>
            </div>
            <p v-else class="empty-hint">练习题目生成中，请稍后查看</p>
            <div v-if="practiceSession.status === 'completed'" style="text-align: center; margin-top: 24px">
              <el-button type="success" @click="router.back()">练习完成，返回查看报告</el-button>
            </div>
          </div>
          <div v-else class="empty-hint">练习会话未找到</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { learningApi } from '@/api/learning'
import type { StageInfo } from '@/types/learning'

const router = useRouter()
const route = useRoute()

// ============================================================
//  Diagnosis form state
// ============================================================
const subjectId = ref('')
const gradeLevel = ref(7)
const textbookVersionId = ref('')
const questionText = ref('')
const originalAnswer = ref('')
const selectedErrorTags = ref<string[]>([])
const errorTagOptions = ['计算错误', '概念不清', '审题失误', '公式记错', '步骤遗漏', '不会做', '单位/格式错误']

const subjects = ref<Array<{ id: string; name: string }>>([])
const running = ref(false)
const started = ref(false)

const stages = ref<StageInfo[]>([
  { stage: 1, name: '知识点定位', status: 'pending' },
  { stage: 2, name: '教材检索', status: 'pending' },
  { stage: 3, name: '错例分析', status: 'pending' },
  { stage: 4, name: 'AI诊断', status: 'pending' },
  { stage: 5, name: '保存报告', status: 'pending' },
])
const progress = ref(0)
const reportSections = ref<Array<{ title: string; content: string; streaming: boolean }>>([])
const sources = ref<Array<{ content: string; score?: number; title?: string }>>([])
const diagnosisDone = ref(false)
const diagnosisError = ref('')
const reportId = ref('')
const currentSection = ref('')

// ============================================================
//  History state
// ============================================================
const historyList = ref<any[]>([])
const historyLoading = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyTotal = ref(0)

// ============================================================
//  Report detail state
// ============================================================
const reportDetail = ref<any>(null)
const reportLoading = ref(false)

// ============================================================
//  Practice state
// ============================================================
const practiceSession = ref<any>(null)
const practiceLoading = ref(false)
const practiceAnswerStates = reactive<Record<number, { answer: string; submitted: boolean; correct: boolean; encouragement: string; submitting: boolean }>>({})

// ============================================================
//  Methods
// ============================================================
function toggleErrorTag(tag: string) {
  const idx = selectedErrorTags.value.indexOf(tag)
  if (idx >= 0) selectedErrorTags.value.splice(idx, 1)
  else selectedErrorTags.value.push(tag)
}

function onSubjectChange(_val: string) {}

function renderMarkdown(text: string): string {
  if (!text) return ''
  return text
    .replace(/### (.+)/g, '<strong>$1</strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\$\$(.+?)\$\$/g, '<em>$1</em>')
    .replace(/\$(.+?)\$/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}

async function startDiagnosis() {
  if (!questionText.value.trim()) return
  running.value = true
  started.value = true
  diagnosisDone.value = false
  diagnosisError.value = ''
  progress.value = 0
  reportSections.value = []
  sources.value = []

  const req = {
    question_text: questionText.value,
    subject_info: `初中数学 ${gradeLevel.value}年级`,
    subject_id: subjectId.value || null,
    grade_level: gradeLevel.value ? String(gradeLevel.value) : null,
    textbook_version_id: textbookVersionId.value || null,
    error_tags: selectedErrorTags.value.length ? selectedErrorTags.value : null,
    original_answer: originalAnswer.value || null,
    kp_code: null,
    original_images: null,
  }

  try {
    const csrfToken = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)?.[1] || ''
    const response = await fetch('/api/v1/learning/analyze/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify(req),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const lines = part.split('\n')
        let eventType = ''
        let dataStr = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7)
          if (line.startsWith('data: ')) dataStr = line.slice(6)
        }
        if (!dataStr) continue
        try {
          const data = JSON.parse(dataStr)
          handleSSEEvent(eventType, data)
        } catch { /* skip malformed */ }
      }
    }
  } catch (e: any) {
    diagnosisError.value = `诊断失败：${e.message || '服务暂时不可用'}。请检查模型配置后重试。`
    ElMessage.error(diagnosisError.value)
  } finally {
    running.value = false
  }
}

function handleSSEEvent(type: string, data: any) {
  switch (type) {
    case 'stage': {
      const idx = data.stage - 1
      if (idx >= 0 && idx < stages.value.length) stages.value[idx].status = data.status
      break
    }
    case 'progress':
      progress.value = data.percent
      break
    case 'content': {
      const section = data.section || '诊断报告'
      const text = data.text || ''
      if (section !== currentSection.value) {
        currentSection.value = section
        const prev = reportSections.value[reportSections.value.length - 1]
        if (prev) prev.streaming = false
        reportSections.value.push({ title: section, content: '', streaming: true })
      }
      const last = reportSections.value[reportSections.value.length - 1]
      if (last) last.content += text
      break
    }
    case 'sources':
      sources.value = data.documents || []
      break
    case 'done':
      reportId.value = data.report_id || ''
      diagnosisDone.value = !diagnosisError.value
      progress.value = 1
      const last = reportSections.value[reportSections.value.length - 1]
      if (last) last.streaming = false
      break
    case 'error':
      diagnosisError.value = data.message || '诊断出错，请稍后重试'
      diagnosisDone.value = false
      ElMessage.error(diagnosisError.value)
      break
  }
}

async function startPractice() {
  if (!reportId.value) { ElMessage.warning('请等待诊断完成'); return }
  try {
    const res = await learningApi.startPractice(reportId.value) as any
    const data = res?.data?.data || res?.data
    const sessionId = data?.id
    if (sessionId) {
      ElMessage.success('靶向练习已生成')
      router.push(`/learning/practice/${sessionId}`)
    } else {
      ElMessage.warning('练习生成失败，请重试')
    }
  } catch { ElMessage.warning('练习生成功能即将上线，请稍后重试') }
}

async function copyReport() {
  const text = reportSections.value.map(s => `${s.title}\n${s.content}`).join('\n\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function rateReport(rating: 'useful' | 'useless') {
  if (!reportId.value) return
  try {
    await learningApi.submitFeedback({ report_id: reportId.value, rating })
    ElMessage.success('感谢反馈')
  } catch {
    ElMessage.warning('反馈提交失败')
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await learningApi.listReports({ page: historyPage.value, page_size: historyPageSize.value }) as any
    const data = res?.data?.data || res?.data || {}
    historyList.value = data.items || []
    historyTotal.value = data.total || 0
  } catch {
    ElMessage.warning('加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

async function loadReportDetail() {
  const id = route.params.id as string
  if (!id) return
  reportLoading.value = true
  try {
    const res = await learningApi.getReport(id) as any
    reportDetail.value = res?.data?.data || res?.data
  } catch {
    ElMessage.warning('加载报告失败')
  } finally {
    reportLoading.value = false
  }
}

async function loadPracticeSession() {
  const id = route.params.id as string
  if (!id) return
  practiceLoading.value = true
  try {
    const res = await learningApi.getPracticeSession(id) as any
    const session = res?.data?.data || res?.data
    if (session) {
      practiceSession.value = session
      // Initialize answer states for each exercise
      if (session.exercises) {
        for (const ex of session.exercises) {
          const alreadySubmitted = session.answers_submitted?.find((a: any) => a.idx === ex.idx)
          practiceAnswerStates[ex.idx] = {
            answer: alreadySubmitted?.answer || '',
            submitted: !!alreadySubmitted,
            correct: alreadySubmitted?.correct || false,
            encouragement: alreadySubmitted ? (alreadySubmitted.correct ? '回答正确！' : '看一下正确答案的思路吧') : '',
            submitting: false,
          }
        }
      }
    }
  } catch {
    ElMessage.warning('加载练习会话失败')
  } finally {
    practiceLoading.value = false
  }
}

async function submitAnswer(exerciseIdx: number) {
  const state = practiceAnswerStates[exerciseIdx]
  if (!state || !state.answer.trim()) return
  state.submitting = true
  try {
    const res = await learningApi.submitPracticeAnswer(
      practiceSession.value.id,
      { exercise_idx: exerciseIdx, answer: state.answer }
    ) as any
    const result = res?.data?.data || res?.data
    if (result) {
      state.submitted = true
      state.correct = result.correct
      state.encouragement = result.encouragement
      state.submitting = false
      // Update session stats
      practiceSession.value.exercises_completed = result.exercises_completed
      practiceSession.value.exercises_correct = result.exercises_correct
      practiceSession.value.status = result.status
      ElMessage.success(result.correct ? '回答正确！' : '已提交，看看正确答案')
    }
  } catch {
    ElMessage.warning('提交失败，请重试')
    state.submitting = false
  }
}

// ============================================================
//  Init
// ============================================================
onMounted(async () => {
  // Load subjects for the diagnosis form
  try {
    const res = await fetch('/api/v1/learning/subjects', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}` },
    })
    if (res.ok) {
      const body = await res.json()
      subjects.value = body?.data?.items || body?.data || []
    }
  } catch { /* silent */ }
  if (subjects.value.length === 0) {
    subjects.value = [{ id: '', name: '数学（初中）' }]
  }

  // Route-aware init
  if (route.name === 'LearningHistory') {
    loadHistory()
  } else if (route.name === 'LearningReport') {
    loadReportDetail()
  } else if (route.name === 'LearningPractice') {
    loadPracticeSession()
  }
})
</script>

<style lang="scss" scoped>
.diagnosis-page {
  display: flex;
  gap: 0;
  height: calc(100vh - 60px - 44px);
  margin: -22px;
}

// ==================== Diagnosis ====================
.input-panel {
  width: 340px;
  min-width: 340px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
  border-right: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  flex-direction: column;
  overflow-y: auto;

  .panel-header {
    padding: 20px 20px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    h2 {
      font-size: 16px;
      font-weight: 600;
      color: #1f2937;
      margin: 0;
    }
  }

  .panel-body { padding: 0 20px 20px; flex: 1; }
}

.diagnose-btn { width: 100%; margin-top: 8px; }
.hint { text-align: center; font-size: 12px; color: #9ca3af; margin-top: 8px; }

.symptom-tags {
  display: flex; flex-wrap: wrap; gap: 6px;
  .symptom-tag { cursor: pointer; user-select: none; }
}

.report-panel { flex: 1; overflow-y: auto; padding: 24px 32px; }

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; text-align: center; color: #9ca3af;
  .empty-icon { font-size: 56px; margin-bottom: 16px; opacity: 0.4; }
  h3 { font-size: 18px; color: #6b7280; margin-bottom: 12px; }
  p { font-size: 14px; line-height: 1.8; max-width: 360px; }
}

.report-content { max-width: 800px; margin: 0 auto; }

.stage-bar {
  display: flex; gap: 16px; margin-bottom: 12px;
  .stage-item {
    display: flex; align-items: center; gap: 6px; font-size: 12px; color: #9ca3af;
    .stage-dot { width: 6px; height: 6px; border-radius: 50%; background: #e5e7eb; }
    &.active { color: #2196f3; .stage-dot { background: #2196f3; } }
    &.done { color: #52c41a; .stage-dot { background: #52c41a; } }
  }
}

.stage-progress { margin-bottom: 24px; }
.diagnosis-error { margin-bottom: 16px; border-radius: 12px; }

.report-card {
  background: #fff; border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px; padding: 20px 24px; margin-bottom: 14px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
  h4 { font-size: 14px; font-weight: 600; color: #1f2937; margin-bottom: 12px; }
  .card-body { font-size: 14px; line-height: 1.8; color: #4b5563; }
  &.stream { border-color: rgba(33, 150, 243, 0.3); }
}

.typing-cursor { color: #2196f3; font-weight: 700; animation: blink 1s step-end infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.sources-card {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 14px;
  h4 { font-size: 13px; font-weight: 600; color: #6b7280; margin-bottom: 10px; }
  .source-item { display: flex; gap: 10px; padding: 6px 0; font-size: 13px; line-height: 1.6;
    .source-title { font-weight: 600; color: #2196f3; min-width: 60px; }
    .source-text { color: #4b5563; }
  }
}

.action-bar { display: flex; gap: 8px; padding-top: 16px; border-top: 1px solid #f3f4f6; margin-top: 20px; }

// ==================== History ====================
.history-page {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    h2 { font-size: 18px; font-weight: 600; color: #1f2937; margin: 0; }
  }
}
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }

// ==================== Report Detail ====================
.report-detail-page {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  .page-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
    h2 { font-size: 18px; font-weight: 600; color: #1f2937; margin: 0; }
  }
  .report-detail-body { max-width: 800px; }
  .report-meta { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
  .meta-time { font-size: 13px; color: #9ca3af; }
  .report-card {
    background: #fff; border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px; padding: 20px 24px; margin-bottom: 14px;
    h4 { font-size: 14px; font-weight: 600; color: #1f2937; margin-bottom: 12px; }
    .card-body { font-size: 14px; line-height: 1.8; color: #4b5563; }
    p { font-size: 14px; color: #4b5563; }
  }
}

// ==================== Practice ====================
.practice-page {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  .page-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
    h2 { font-size: 18px; font-weight: 600; color: #1f2937; margin: 0; }
  }
  .practice-body { max-width: 700px; }
  .practice-info { margin-bottom: 16px; display: flex; align-items: center; }
  .exercise-card {
    background: #fff; border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
    h4 { font-size: 14px; font-weight: 600; color: #1f2937; margin-bottom: 8px; }
    p { font-size: 14px; color: #4b5563; line-height: 1.7; }
    .hints { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
    .question-text { white-space: pre-wrap; }
    .answer-input { margin-top: 12px; border-top: 1px solid #e5e7eb; padding-top: 12px; }
    .answer-feedback {
      margin-top: 12px; border-top: 1px solid #e5e7eb; padding: 12px;
      background: #fef2f2; border-radius: 6px;
      &.correct { background: #f0fdf4; }
    }
  }
  .empty-hint { text-align: center; color: #9ca3af; padding: 40px 0; }
}
</style>
