<template>
  <section class="reader-view">
    <header class="reader-header">
      <div class="reader-title-wrap">
        <el-button text @click="router.back()"><el-icon><ArrowLeft /></el-icon>返回文档</el-button>
        <div>
          <p class="eyebrow">READING DESK · EVIDENCE FIRST</p>
          <h1>{{ documentTitle }}</h1>
          <p class="reader-meta">阅读、标注、理解，并把关键段落沉淀到知识中心。</p>
        </div>
      </div>
      <div class="reader-actions"><el-tag v-if="document" effect="plain">{{ documentType }}</el-tag><el-button @click="router.push('/knowledge')">去知识中心</el-button></div>
    </header>
    <el-alert v-if="loadError" type="error" :closable="false" show-icon>{{ loadError }}</el-alert>
    <div v-if="loading" class="loading-state"><el-skeleton :rows="10" animated /></div>
    <div v-else class="reader-layout">
      <article class="document-paper">
        <div class="paper-topline"><span>原文</span><span>{{ paragraphs.length }} 个段落 · {{ annotations.length }} 条标注</span></div>
        <div v-if="paragraphs.length" class="paper-content"><p v-for="(paragraph, index) in paragraphs" :key="`${index}-${paragraph.slice(0, 12)}`" :class="{ selected: selectedQuote === paragraph }" @click="selectParagraph(paragraph)">{{ paragraph }}</p></div>
        <el-empty v-else description="暂无可阅读文本，文档可能仍在处理中" :image-size="80" />
      </article>
      <aside class="annotation-desk">
        <div class="desk-heading"><div><span class="section-kicker">ANNOTATION DESK</span><h2>标注台</h2></div><el-tag effect="plain">{{ annotations.length }}</el-tag></div>
        <el-tabs v-model="activeTab" class="desk-tabs"><el-tab-pane name="note"><template #label>笔记 <small>{{ countByKind('note') }}</small></template></el-tab-pane><el-tab-pane name="understanding"><template #label>理解 <small>{{ countByKind('understanding') }}</small></template></el-tab-pane><el-tab-pane name="inbox"><template #label>入库</template></el-tab-pane></el-tabs>
        <div v-if="activeTab !== 'inbox'" class="annotation-list"><article v-for="item in visibleAnnotations" :key="item.id" class="annotation-item"><blockquote v-if="item.quote">{{ item.quote }}</blockquote><p>{{ item.body }}</p><small v-if="item.question">我的问题：{{ item.question }}</small><div class="annotation-footer"><time>{{ formatDate(item.created_at) }}</time><el-button link type="danger" @click="removeAnnotation(item)">删除</el-button></div></article><el-empty v-if="!visibleAnnotations.length" description="这一类还没有标注" :image-size="56" /></div>
        <div v-if="activeTab !== 'inbox'" class="composer"><div class="composer-label"><span>{{ activeTab === 'note' ? '记录一条笔记' : '写下你的理解' }}</span><div><el-button v-if="selectedQuote" link type="primary" @click="explainWithAi">让 AI 解释</el-button><el-button v-if="selectedQuote" link type="primary" @click="selectedQuote = ''">清除引用</el-button></div></div><blockquote v-if="selectedQuote" class="selected-quote">{{ selectedQuote }}</blockquote><el-input v-model="body" type="textarea" :rows="4" :placeholder="activeTab === 'note' ? '这段内容对我有什么用？' : '用自己的话解释这段内容，或记录仍然不清楚的地方。'" /><el-input v-if="activeTab === 'understanding'" v-model="question" class="question-input" placeholder="我的问题（可选）" /><el-button type="primary" :loading="saving" :disabled="!body.trim()" @click="saveAnnotation">保存到标注台</el-button></div>
        <div v-else class="inbox-panel"><div class="inbox-intro"><strong>把阅读结果沉淀为知识卡片</strong><p>选中原文后填写标题和你的结论，保存后会进入知识中心审核队列。</p></div><blockquote v-if="selectedQuote" class="selected-quote">{{ selectedQuote }}</blockquote><el-input v-model="knowledgeTitle" placeholder="知识卡片标题，例如：个人工作台需要绑定真实任务" /><el-input v-model="knowledgeDefinition" type="textarea" :rows="6" class="inbox-definition" placeholder="写下可复用的定义、判断或结论" /><el-button type="primary" :loading="knowledgeSaving" :disabled="!knowledgeTitle.trim() || !knowledgeDefinition.trim()" @click="saveToKnowledge">保存到知识中心</el-button><el-button v-if="!selectedQuote" link type="primary" @click="activeTab = 'understanding'">先选择一段原文</el-button></div>
      </aside>
    </div>
    <el-dialog v-model="aiVisible" title="AI 理解这段内容" width="620px" destroy-on-close><blockquote class="ai-quote">{{ selectedQuote }}</blockquote><el-alert v-if="aiError" type="warning" :closable="false" show-icon>{{ aiError }}</el-alert><el-input v-model="aiQuestion" type="textarea" :rows="4" placeholder="你想让 AI 如何解释这段内容？" /><div v-if="aiAnswer" class="ai-answer"><strong>AI 回答</strong><p>{{ aiAnswer }}</p></div><template #footer><el-button @click="aiVisible = false">关闭</el-button><el-button type="primary" :loading="aiLoading" :disabled="!aiQuestion.trim()" @click="runAiExplain">发送给 AI</el-button></template></el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getDocument, getDocumentFullText } from '@/api/document'
import { annotationApi } from '@/api/annotation'
import { knowledgeApi } from '@/api/knowledge'
import { getAsyncChatJobStatus, getConversationMessages, submitAsyncChatJob } from '@/api/chat'
import { useWorkspaceStore } from '@/stores/workspace'
import { useDatasetStore } from '@/stores/dataset'
import type { Document as DocumentType } from '@/types'
import type { DocumentAnnotation, DocumentAnnotationKind } from '@/types/annotation'

const route = useRoute(); const router = useRouter(); const documentId = computed(() => String(route.params.documentId || ''))
const workspaceStore = useWorkspaceStore(); const datasetStore = useDatasetStore(); const document = ref<DocumentType | null>(null); const annotations = ref<DocumentAnnotation[]>([]); const loading = ref(true); const saving = ref(false); const knowledgeSaving = ref(false); const loadError = ref(''); const fullText = ref(''); const activeTab = ref<DocumentAnnotationKind | 'inbox'>('note'); const selectedQuote = ref(''); const body = ref(''); const question = ref(''); const knowledgeTitle = ref(''); const knowledgeDefinition = ref(''); const aiVisible = ref(false); const aiLoading = ref(false); const aiError = ref(''); const aiQuestion = ref(''); const aiAnswer = ref('')
const documentTitle = computed(() => document.value?.name || '文档阅读台')
const documentType = computed(() => String(document.value?.type || 'document').toUpperCase())
const paragraphs = computed(() => fullText.value.split(/\n{2,}|\n(?=\S)/).map(item => item.trim()).filter(Boolean)); const visibleAnnotations = computed(() => annotations.value.filter(item => item.kind === activeTab.value))
function countByKind(kind: DocumentAnnotationKind) { return annotations.value.filter(item => item.kind === kind).length }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
function selectParagraph(paragraph: string) {
  // 优先保留用户用鼠标/触控选中的片段；没有选区时才回退到整段引用。
  // 这样既接近参考产品的“证据摘录”体验，也兼容移动端直接点击段落。
  const selection = window.getSelection?.()
  const selectedText = selection?.toString().trim() || ''
  const anchor = selection?.anchorNode
  const paper = anchor instanceof Node ? anchor.parentElement?.closest('.paper-content') : null
  const quote = selectedText && paper ? selectedText : paragraph
  selectedQuote.value = quote
  ElMessage.info(quote === paragraph ? '已引用这段原文，可在右侧补充笔记或理解' : '已引用选中的原文片段，可在右侧补充笔记或理解')
}
async function load() { if (!documentId.value) return; loading.value = true; try { const [docResult, textResult, annotationResult] = await Promise.all([getDocument(documentId.value), getDocumentFullText(documentId.value), annotationApi.list(documentId.value)]); document.value = (docResult as any).data || docResult as any; fullText.value = textResult; annotations.value = annotationResult.items || [] } catch (error) { loadError.value = error instanceof Error ? error.message : '文档阅读台加载失败' } finally { loading.value = false } }
async function saveAnnotation() { if (activeTab.value === 'inbox' || !documentId.value || !body.value.trim()) return; saving.value = true; try { const result = await annotationApi.create(documentId.value, { kind: activeTab.value, quote: selectedQuote.value, body: body.value.trim(), question: question.value.trim() || undefined }); annotations.value.unshift(result); body.value = ''; question.value = ''; selectedQuote.value = ''; ElMessage.success(activeTab.value === 'note' ? '笔记已保存' : '理解已保存') } catch (error) { ElMessage.error(error instanceof Error ? error.message : '标注保存失败') } finally { saving.value = false } }
async function removeAnnotation(item: DocumentAnnotation) { try { await annotationApi.remove(documentId.value, item.id); annotations.value = annotations.value.filter(entry => entry.id !== item.id); ElMessage.success('标注已删除') } catch (error) { ElMessage.error(error instanceof Error ? error.message : '标注删除失败') } }
async function saveToKnowledge() { if (!workspaceStore.currentWorkspaceId || !knowledgeTitle.value.trim() || !knowledgeDefinition.value.trim()) return; knowledgeSaving.value = true; try { const item = await knowledgeApi.create({ workspace_id: workspaceStore.currentWorkspaceId, title: knowledgeTitle.value.trim(), item_type: 'reading_note', definition: knowledgeDefinition.value.trim(), conclusions: [knowledgeDefinition.value.trim()], confidence: 0.7, metadata: { source_document_id: documentId.value, source: 'reading_desk' } }); if (selectedQuote.value) await knowledgeApi.addEvidence(item.id, { document_id: documentId.value, quote: selectedQuote.value }); knowledgeTitle.value = ''; knowledgeDefinition.value = ''; ElMessage.success('已保存到知识中心，等待审核'); activeTab.value = 'note' } catch (error) { ElMessage.error(error instanceof Error ? error.message : '知识卡片保存失败') } finally { knowledgeSaving.value = false } }
async function explainWithAi() { if (!selectedQuote.value) return ElMessage.warning('请先点击一段原文'); aiVisible.value = true; aiError.value = ''; aiAnswer.value = ''; aiQuestion.value = '请用清晰、具体的语言解释这段内容，并说明它对我的工作有什么启发。'; if (!datasetStore.datasets.length) await datasetStore.fetchDatasets({ silent: true }) }
async function runAiExplain() { const datasetId = document.value?.dataset_id || datasetStore.datasets[0]?.id; if (!datasetId || !aiQuestion.value.trim()) { aiError.value = '当前工作空间没有可用知识库，请先创建或导入一个知识库。'; return } aiLoading.value = true; aiError.value = ''; aiAnswer.value = ''; try { const submitted = await submitAsyncChatJob({ dataset_id: datasetId, query: `${aiQuestion.value.trim()}\n\n原文：${selectedQuote.value}` }); const payload = submitted?.data || submitted; const jobId = String(payload?.job_id || ''); if (!jobId) throw new Error('未获取到 AI 任务 ID'); for (let attempt = 0; attempt < 80; attempt += 1) { await new Promise(resolve => window.setTimeout(resolve, 1500)); const statusResponse = await getAsyncChatJobStatus(jobId); const statusPayload = statusResponse?.data || statusResponse; const status = String(statusPayload?.status || '').toUpperCase(); if (status === 'FAILURE') throw new Error(String(statusPayload?.error || 'AI 任务执行失败')); if (status === 'SUCCESS') { const result = statusPayload?.result || {}; const conversationId = String(result.conversation_id || ''); if (conversationId) { const messagesResponse = await getConversationMessages(conversationId); const rawMessages = Array.isArray(messagesResponse) ? messagesResponse : (messagesResponse?.data || messagesResponse?.items || []); const latest = [...rawMessages].reverse().find((message: any) => message?.role === 'assistant'); aiAnswer.value = String(latest?.content || result.answer || result.content || '任务已完成，但没有返回回答。') } else aiAnswer.value = String(result.answer || result.content || '任务已完成，但没有返回回答。'); return } } throw new Error('AI 回答超时，请进入完整问答页查看') } catch (error) { aiError.value = error instanceof Error ? error.message : 'AI 理解失败，请稍后重试' } finally { aiLoading.value = false } }
onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); await load() })
</script>

<style scoped lang="scss">
.reader-view{max-width:1500px;margin:0 auto}.reader-header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:20px}.reader-title-wrap{display:flex;gap:18px;align-items:flex-start}.reader-title-wrap>.el-button{margin-top:3px}.reader-header h1{margin:0 0 8px;font-family:Georgia,'Times New Roman',serif;font-size:clamp(28px,3.4vw,44px);letter-spacing:-.045em}.eyebrow,.section-kicker{margin:0 0 8px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.16em}.reader-meta{margin:0;color:var(--el-text-color-secondary)}.reader-actions{display:flex;gap:10px;align-items:center;padding-top:20px}.reader-layout{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:18px;align-items:start}.document-paper,.annotation-desk{border:1px solid rgba(112,74,198,.14);border-radius:20px;background:rgba(255,255,255,.9);box-shadow:0 14px 34px rgba(79,51,133,.06)}.document-paper{min-height:calc(100vh - 210px);padding:26px 44px}.paper-topline{display:flex;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid rgba(112,74,198,.12);color:var(--el-text-color-secondary);font-size:12px}.paper-content{padding-top:24px}.paper-content p{margin:0;padding:12px 14px;border-left:3px solid transparent;color:#332b3d;font-size:17px;line-height:2;cursor:pointer;border-radius:0 10px 10px 0;transition:.18s}.paper-content p:hover,.paper-content p.selected{border-left-color:var(--el-color-primary);background:#f7f2ff}.annotation-desk{position:sticky;top:18px;padding:22px}.desk-heading{display:flex;justify-content:space-between;align-items:flex-start}.desk-heading h2{margin:4px 0 0;font-size:21px}.desk-tabs{margin-top:12px}.desk-tabs :deep(.el-tabs__item){height:38px}.desk-tabs small{margin-left:4px;color:var(--el-color-primary)}.annotation-list{max-height:390px;overflow:auto}.annotation-item{padding:14px 0;border-bottom:1px solid rgba(112,74,198,.1)}.annotation-item blockquote,.selected-quote{margin:0 0 10px;padding:9px 11px;border-left:3px solid #a77be8;background:#faf7ff;color:#75658a;font-size:12px;line-height:1.6}.annotation-item p{margin:0;color:var(--el-text-color-primary);line-height:1.65}.annotation-item>small{display:block;margin-top:7px;color:var(--el-text-color-secondary);line-height:1.5}.annotation-footer{display:flex;justify-content:space-between;align-items:center;margin-top:8px;color:var(--el-text-color-secondary);font-size:11px}.composer{margin-top:18px;padding-top:16px;border-top:1px solid rgba(112,74,198,.12)}.composer-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;color:var(--el-text-color-primary);font-size:13px;font-weight:700}.question-input{margin-top:9px}.composer>.el-button{width:100%;margin-top:10px}.loading-state{padding:28px;background:#fff;border-radius:18px}.inbox-panel{display:grid;gap:12px;padding-top:14px}.inbox-intro{padding:13px;border-radius:12px;background:#faf7ff}.inbox-intro strong{color:#4c3284}.inbox-intro p{margin:6px 0 0;color:var(--el-text-color-secondary);font-size:12px;line-height:1.6}.inbox-definition{margin-top:2px}.inbox-panel>.el-button{width:100%;margin-left:0}.ai-quote{margin:0 0 16px;padding:12px 14px;border-left:3px solid #8d5ce6;border-radius:0 10px 10px 0;background:#faf7ff;color:#75658a;line-height:1.7}.ai-answer{margin-top:14px;padding:14px;border:1px solid rgba(112,74,198,.14);border-radius:14px;background:#faf8ff}.ai-answer p{margin:8px 0 0;white-space:pre-wrap;line-height:1.7}@media(max-width:1000px){.reader-layout{grid-template-columns:1fr}.annotation-desk{position:static}.document-paper{min-height:auto;padding:24px}}@media(max-width:620px){.reader-header{display:block}.reader-actions{padding-top:14px}.reader-title-wrap{display:block}.reader-title-wrap>.el-button{margin-bottom:12px}.document-paper{padding:18px}.paper-content p{font-size:15px}}
</style>
<style scoped lang="scss">
.paper-content p {
  cursor: text;
  user-select: text;
}
</style>
