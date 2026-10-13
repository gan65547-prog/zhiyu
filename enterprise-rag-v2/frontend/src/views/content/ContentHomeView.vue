<template>
  <section class="content-home">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / 内容中心
        </p><h1>内容中心</h1><p class="subtitle">
          把研究洞察转成选题和可审核草稿。
        </p>
      </div><div class="header-actions"><el-button
        type="primary"
        plain
        @click="openCreate"
      >
        新建草稿
      </el-button><el-button
        type="primary"
        @click="topicDialog = true"
      >
        新建选题
      </el-button></div>
    </header>
    <div class="content-summary">
      <article v-for="metric in summaryMetrics" :key="metric.label" class="summary-card" :class="metric.tone">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.detail }}</small>
      </article>
    </div>
    <div class="content-grid">
      <el-card shadow="never">
        <template #header>
          <strong>选题池</strong>
        </template><el-empty
          v-if="!topics.length"
          description="暂无选题"
        /><div
          v-for="topic in topics"
          v-else
          :key="topic.id"
          class="topic-row"
        >
          <div><strong>{{ topic.title }}</strong><p>{{ topic.brief || '未填写简介' }}</p></div><el-tag :type="topicStatusType(topic.status)">{{ topicStatusLabel(topic.status) }}</el-tag>
        </div>
      </el-card>
      <el-card shadow="never">
        <template #header>
          <strong>草稿审核</strong>
        </template><el-empty
          v-if="!drafts.length"
          description="暂无草稿"
        /><div
          v-for="draft in drafts"
          v-else
          :key="draft.id"
          class="draft-row"
        >
          <div><strong>{{ draft.title }}</strong><p>{{ draft.body.slice(0, 100) || '空草稿' }}</p></div><div>
            <el-tag :type="draft.review_status === 'approved' ? 'success' : draft.review_status === 'rejected' ? 'danger' : 'warning'">
              {{ reviewLabel(draft.review_status) }}
            </el-tag><div
              v-if="draft.review_status === 'pending'"
              class="actions"
            >
              <el-button
                text
                type="success"
                @click="review(draft, 'approved')"
              >
                通过
              </el-button><el-button
                text
                type="danger"
                @click="review(draft, 'rejected')"
              >
                驳回
              </el-button>
            </div><el-button
              v-if="draft.review_status !== 'approved'"
              text
              type="primary"
              @click="openEdit(draft)"
            >编辑</el-button><el-button
              text
              type="info"
              @click="openRewrite(draft)"
            >改写草稿</el-button><el-button
              v-if="draft.review_status === 'approved'"
              text
              type="primary"
              @click="openPublish(draft)"
            >
              记录发布
            </el-button><el-button
              v-if="draft.review_status === 'approved'"
              text
              type="warning"
              @click="openSchedule(draft)"
            >
              排期
            </el-button><el-dropdown trigger="click" @command="(format: 'markdown' | 'json') => exportDraft(draft, format)">
              <el-button text type="primary">导出</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="markdown">下载 Markdown 发布包</el-dropdown-item>
                  <el-dropdown-item command="json">下载 JSON 归档包</el-dropdown-item>
                  <el-dropdown-item divided @click="copyDraft(draft)">复制正文</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-card>
    </div>
    <el-card shadow="never" class="credentials-card">
      <template #header><div class="section-header"><strong>发布凭据</strong><el-button type="primary" link @click="credentialDialog = true">新增凭据</el-button></div></template>
      <el-alert v-if="credentials.length" type="info" :closable="false" show-icon>凭据仅保存加密密文；保存凭据不代表发布成功，发布状态以连接器返回和人工确认结果为准。</el-alert>
      <el-table v-if="credentials.length" :data="credentials" size="small">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="平台" width="130"><template #default="{ row }">{{ platformLabel(row.platform) }}</template></el-table-column>
        <el-table-column prop="credential_hint" label="提示" min-width="160" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ credentialStatusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="180"><template #default="{ row }"><el-button v-if="row.status === 'active'" text type="primary" :loading="testingCredentialId === row.id" @click="testCredential(row)">测试连接</el-button><el-button v-if="row.status === 'active'" text type="danger" @click="revokeCredential(row)">撤销</el-button></template></el-table-column>
      </el-table>
      <el-empty v-else description="暂无发布凭据；人工确认发布不需要配置凭据" />
    </el-card>
    <el-card
      shadow="never"
      class="calendar-card"
    >
      <template #header>
        <div class="section-header"><strong>发布日历</strong><el-button type="primary" link @click="metricImportDialog = true">批量导入指标</el-button></div>
      </template>
      <el-table
        v-if="publishes.length"
        :data="publishes"
        size="small"
      >
        <el-table-column
          label="发布时间"
          min-width="190"
        ><template #default="{ row }">{{ formatDateTime(row.published_at) }}</template></el-table-column>
        <el-table-column
          label="平台"
          width="140"
        ><template #default="{ row }">{{ platformLabel(row.platform) }}</template></el-table-column>
        <el-table-column
          prop="status"
          label="状态"
          width="110"
        ><template #default="{ row }"><el-tag size="small" :type="publishStatusType(row.status)">{{ publishStatusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="曝光/点击" min-width="150">
          <template #default="{ row }">
            {{ row.latest_metrics?.impressions ?? '-' }} / {{ row.latest_metrics?.clicks ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'ready'"
              text
              type="success"
              @click="openConfirmPublish(row)"
              >确认已发布</el-button>
            <el-button
              v-if="row.status === 'published'"
              text
              type="primary"
              @click="openRetrospective(row)"
            >复盘</el-button>
            <el-button
              v-if="row.status === 'published'"
              text
              type="warning"
              @click="openMetric(row)"
            >录入指标</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        description="暂无发布记录"
      />
    </el-card>
    <el-dialog
      v-model="topicDialog"
      title="新建选题"
      width="480px"
    >
      <el-form label-width="70px">
        <el-form-item label="标题">
          <el-input v-model="topicForm.title" />
        </el-form-item><el-form-item label="简介">
          <el-input
            v-model="topicForm.brief"
            type="textarea"
          />
        </el-form-item>
      </el-form><template #footer>
        <el-button @click="topicDialog = false">
          取消
        </el-button><el-button
          type="primary"
          @click="createTopic"
        >
          创建
        </el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="rewriteDialog" title="改写草稿" width="700px">
      <el-form label-width="90px">
        <el-form-item label="目标平台">
          <el-checkbox-group v-model="rewritePlatforms">
            <el-checkbox label="x">X / 短帖</el-checkbox>
            <el-checkbox label="website">网站</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="生成方式">
          <el-radio-group v-model="rewriteMode">
            <el-radio label="deterministic">规则改写</el-radio>
            <el-radio label="model">模型增强（需审核）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <div v-if="rewriteVariants.length" class="rewrite-results">
        <el-card v-for="variant in rewriteVariants" :key="variant.platform" shadow="never">
          <template #header><strong>{{ platformLabel(variant.platform) }}</strong></template>
          <pre>{{ variant.body }}</pre>
        </el-card>
      </div>
      <template #footer>
        <el-button @click="rewriteDialog = false">关闭</el-button>
        <el-button type="primary" :loading="rewriting" @click="rewriteDraft">生成改写</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="draftDialog"
      :title="editingDraft ? '编辑内容草稿' : '新建内容草稿'"
      width="620px"
    >
      <el-form label-width="70px">
        <el-form-item label="选题">
          <el-select
            v-model="draftForm.topic_id"
            clearable
            placeholder="可选"
            style="width: 100%"
          >
            <el-option
              v-for="topic in topics"
              :key="topic.id"
              :label="topic.title"
              :value="topic.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="draftForm.title" />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input
            v-model="draftForm.body"
            type="textarea"
            :rows="10"
            maxlength="100000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="draftDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="createDraft"
        >{{ editingDraft ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="scheduleDialog"
      title="安排内容发布"
      width="480px"
    >
      <el-form label-width="70px">
        <el-form-item label="平台">
          <el-select v-model="scheduleForm.platform" placeholder="选择已注册连接器" style="width: 100%" @change="scheduleForm.credential_id = ''">
            <el-option v-for="connector in availableConnectors" :key="connector.key" :label="connector.label" :value="connector.key" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="connectorRequiresCredentials(scheduleForm.platform)" label="凭据">
          <el-select v-model="scheduleForm.credential_id" placeholder="选择已保存凭据" style="width: 100%">
            <el-option v-for="credential in credentialsForPlatform(scheduleForm.platform)" :key="credential.id" :label="credential.name" :value="credential.id" />
          </el-select>
          <small v-if="!credentialsForPlatform(scheduleForm.platform).length" class="form-hint">请先在平台数据页配置并测试该平台凭据。</small>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="scheduleForm.scheduled_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择未来时间"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="schedule"
        >确认排期</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="retrospectiveDialog"
      title="内容效果复盘"
      width="620px"
    >
      <template v-if="retrospective">
        <p class="retro-summary">{{ retrospective.summary }}</p>
        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="曝光">{{ retrospective.metric_snapshot.impressions ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="点击率">{{ retrospective.metric_snapshot.ctr ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="互动率">{{ retrospective.metric_snapshot.engagement_rate ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="点击">{{ retrospective.metric_snapshot.clicks ?? '-' }}</el-descriptions-item>
        </el-descriptions>
        <h4>改进建议</h4>
        <ul class="recommendations">
          <li v-for="recommendation in retrospective.recommendations" :key="recommendation">{{ recommendation }}</li>
        </ul>
      </template>
    </el-dialog>
    <el-dialog
      v-model="metricDialog"
      title="录入内容指标"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="曝光"><el-input-number v-model="metricForm.impressions" :min="0" /></el-form-item>
        <el-form-item label="点击"><el-input-number v-model="metricForm.clicks" :min="0" /></el-form-item>
        <el-form-item label="点赞"><el-input-number v-model="metricForm.likes" :min="0" /></el-form-item>
        <el-form-item label="评论"><el-input-number v-model="metricForm.comments" :min="0" /></el-form-item>
        <el-form-item label="分享"><el-input-number v-model="metricForm.shares" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metricDialog = false">取消</el-button>
        <el-button type="primary" @click="saveMetric">保存指标</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="metricImportDialog" title="批量导入内容指标" width="620px">
      <el-alert type="info" :closable="false" show-icon>每条记录需要发布记录 ID 和 ISO 时间；相同发布记录、相同采集时间会自动跳过。</el-alert>
      <el-input v-model="metricImportJson" type="textarea" :rows="10" placeholder='例如 [{"publish_id":"...","collected_at":"2026-08-05T12:00:00Z","metric":{"impressions":100,"clicks":8}}]' />
      <template #footer><el-button @click="metricImportDialog = false">取消</el-button><el-button type="primary" @click="importMetrics">导入</el-button></template>
    </el-dialog>
    <el-dialog v-model="publishDialog" title="记录发布" width="520px" destroy-on-close>
      <el-alert type="info" :closable="false" show-icon class="dialog-note">当前动作记录内容已经发送或准备发送到哪个平台；没有真实连接器时，状态会保留为待确认，不会伪造外部发布成功。</el-alert>
      <el-form label-width="90px" class="credential-form">
        <el-form-item label="平台"><el-select v-model="publishForm.platform" placeholder="选择已注册连接器" style="width:100%" @change="publishForm.credential_id = ''"><el-option v-for="connector in availableConnectors" :key="connector.key" :label="connector.label" :value="connector.key" /></el-select></el-form-item>
        <el-form-item v-if="connectorRequiresCredentials(publishForm.platform)" label="凭据"><el-select v-model="publishForm.credential_id" placeholder="选择已保存凭据" style="width:100%"><el-option v-for="credential in credentialsForPlatform(publishForm.platform)" :key="credential.id" :label="credential.name" :value="credential.id" /></el-select><small v-if="!credentialsForPlatform(publishForm.platform).length" class="form-hint">请先在平台数据页配置并测试该平台凭据。</small></el-form-item>
        <el-form-item label="外部 ID"><el-input v-model="publishForm.externalId" placeholder="可选：平台返回的内容 ID" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="publishDialog = false">取消</el-button><el-button type="primary" :loading="publishing" @click="publish">保存发布记录</el-button></template>
    </el-dialog>
    <el-dialog v-model="confirmDialog" title="确认已发布" width="520px" destroy-on-close>
      <el-alert type="warning" :closable="false" show-icon class="dialog-note">确认后该发布记录会进入平台数据和复盘流程，请确认你已经在外部平台完成发布。</el-alert>
      <el-form label-width="90px"><el-form-item label="外部 ID"><el-input v-model="confirmExternalId" placeholder="可选：平台内容 ID" /></el-form-item></el-form>
      <template #footer><el-button @click="confirmDialog = false">取消</el-button><el-button type="primary" :loading="confirming" @click="confirmPublish">确认已发布</el-button></template>
    </el-dialog>
    <el-dialog v-model="credentialDialog" title="新增发布凭据" width="520px">
      <el-alert type="info" :closable="false" show-icon>凭据只用于已接入的平台连接器，保存凭据不代表发布已成功。</el-alert>
      <el-form label-width="90px" class="credential-form">
        <el-form-item label="平台"><el-select v-model="credentialForm.platform" placeholder="选择平台"><el-option label="X / 短帖" value="x" /><el-option label="网站" value="website" /></el-select></el-form-item>
        <el-form-item label="名称"><el-input v-model="credentialForm.name" placeholder="例如 官方账号" /></el-form-item>
        <el-form-item label="凭据提示"><el-input v-model="credentialForm.hint" placeholder="例如 AppID 末四位" /></el-form-item>
        <el-form-item label="凭据 JSON"><el-input v-model="credentialForm.json" type="textarea" :rows="5" placeholder='例如 {"app_id":"...","app_secret":"..."}' /></el-form-item>
      </el-form>
      <template #footer><el-button @click="credentialDialog = false">取消</el-button><el-button type="primary" @click="createCredential">保存加密凭据</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { contentApi } from '@/api/content'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ContentCredential, ContentDraft, ContentPublishRecord, ContentRetrospective, ContentTopic } from '@/types/content'

const workspaceStore = useWorkspaceStore()
const route = useRoute()
const workspaceId = ref('')
const topics = ref<ContentTopic[]>([])
const drafts = ref<ContentDraft[]>([])
const publishes = ref<ContentPublishRecord[]>([])
const credentials = ref<ContentCredential[]>([])
const connectors = ref<Array<{ key: string; label: string; status: string; requires_credentials?: boolean }>>([])
const topicDialog = ref(false)
const draftDialog = ref(false)
const rewriteDialog = ref(false)
const scheduleDialog = ref(false)
const retrospectiveDialog = ref(false)
const metricDialog = ref(false)
const metricImportDialog = ref(false)
const credentialDialog = ref(false)
const publishDialog = ref(false)
const confirmDialog = ref(false)
const activeDraft = ref<ContentDraft | null>(null)
const activePublish = ref<ContentPublishRecord | null>(null)
const editingDraft = ref<ContentDraft | null>(null)
const rewriting = ref(false)
const rewritePlatforms = ref<string[]>(['website'])
const rewriteMode = ref<'deterministic' | 'model'>('deterministic')
const rewriteVariants = ref<Array<{ platform: string; body: string }>>([])
const retrospective = ref<ContentRetrospective | null>(null)
const metricImportJson = ref('')
const topicForm = ref({ title: '', brief: '' })
const draftForm = ref({ topic_id: '', title: '', body: '' })
const scheduleForm = ref({ platform: '', credential_id: '', scheduled_at: '' })
const metricForm = ref({ impressions: 0, clicks: 0, likes: 0, comments: 0, shares: 0 })
const credentialForm = ref({ platform: '', name: '', hint: '', json: '' })
const publishForm = ref({ platform: 'manual', credential_id: '', externalId: '' })
const confirmExternalId = ref('')
const publishing = ref(false)
const targetLinkHandled = ref(false)
const confirming = ref(false)
const testingCredentialId = ref('')
const summaryMetrics = computed(() => [
  { label: '内容草稿', value: drafts.value.length, detail: '当前工作空间', tone: '' },
  { label: '待审核', value: drafts.value.filter(item => item.review_status === 'pending').length, detail: '需要人工确认', tone: 'warm' },
  { label: '已发布', value: publishes.value.filter(item => item.status === 'published').length, detail: '已确认的发布记录', tone: 'green' },
  { label: '累计曝光', value: formatNumber(publishes.value.reduce((sum, item) => sum + Number(item.latest_metrics?.impressions || 0), 0)), detail: '已回写平台快照', tone: 'accent' },
])
const unavailablePlatforms = new Set(['wechat', 'douyin', 'zhihu'])
const availableConnectors = computed(() => connectors.value.filter((connector) => connector.status === 'available' && !unavailablePlatforms.has(connector.key)))
function showActionError(error: unknown, fallback: string) {
  const message = error instanceof Error && error.message ? error.message : fallback
  ElMessage.error(message)
}
function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN').format(value) }
function formatDateTime(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }) : '未排期' }
function topicStatusLabel(status: string) { return ({ idea: '想法', ready: '待创作', in_progress: '创作中', archived: '已归档' } as Record<string, string>)[status] || status || '待处理' }
function topicStatusType(status: string) { return status === 'archived' ? 'info' : status === 'in_progress' ? 'warning' : status === 'ready' ? 'success' : 'primary' }
function connectorRequiresCredentials(platform: string) { return Boolean(connectors.value.find((connector) => connector.key === platform)?.requires_credentials) }
function credentialsForPlatform(platform: string) { return credentials.value.filter((credential) => credential.platform === platform && credential.status === 'active') }
async function load() {
  if (!workspaceId.value) return
  const results = await Promise.allSettled([
    contentApi.listTopics(workspaceId.value),
    contentApi.listDrafts(workspaceId.value),
    contentApi.listPublishes(workspaceId.value),
    contentApi.listCredentials(workspaceId.value),
    contentApi.listConnectors(),
  ])
  const [topicResult, draftResult, publishResult, credentialResult, connectorResult] = results
  topics.value = topicResult.status === 'fulfilled' ? topicResult.value.items || [] : []
  drafts.value = draftResult.status === 'fulfilled' ? draftResult.value.items || [] : []
  publishes.value = publishResult.status === 'fulfilled' ? publishResult.value.items || [] : []
  credentials.value = credentialResult.status === 'fulfilled' ? (credentialResult.value || []).filter(item => !unavailablePlatforms.has(item.platform)) : []
  connectors.value = connectorResult.status === 'fulfilled' ? connectorResult.value || [] : []
  if (!targetLinkHandled.value && route.query.draft_id) {
    const target = drafts.value.find(item => item.id === String(route.query.draft_id))
    if (target) { targetLinkHandled.value = true; openEdit(target); ElMessage.info('已定位到待审核草稿') }
  }
  if (!targetLinkHandled.value && route.query.publish_id) {
    const target = publishes.value.find(item => item.id === String(route.query.publish_id))
    if (target) { targetLinkHandled.value = true; openConfirmPublish(target); ElMessage.info('已定位到待确认发布记录') }
  }
  if (results.some((result) => result.status === 'rejected')) {
    ElMessage.warning('部分内容数据暂时不可用，已保留可加载内容')
  }
}
async function createTopic() { if (!workspaceId.value || !topicForm.value.title.trim()) return ElMessage.warning('请输入选题标题'); try { await contentApi.createTopic({ workspace_id: workspaceId.value, ...topicForm.value }); topicDialog.value = false; topicForm.value = { title: '', brief: '' }; await load(); ElMessage.success('选题已创建') } catch (error) { showActionError(error, '选题创建失败') } }
async function createDraft() { if (!workspaceId.value || !draftForm.value.title.trim() || !draftForm.value.body.trim()) return ElMessage.warning('请填写草稿标题和正文'); const isEditing = Boolean(editingDraft.value); try { if (editingDraft.value) { await contentApi.updateDraft(editingDraft.value.id, { topic_id: draftForm.value.topic_id || null, title: draftForm.value.title.trim(), body: draftForm.value.body }); } else { await contentApi.createDraft({ workspace_id: workspaceId.value, topic_id: draftForm.value.topic_id || undefined, title: draftForm.value.title.trim(), body: draftForm.value.body }); } draftDialog.value = false; editingDraft.value = null; draftForm.value = { topic_id: '', title: '', body: '' }; ElMessage.success(isEditing ? '草稿已保存' : '草稿已创建'); await load() } catch (error) { showActionError(error, isEditing ? '草稿保存失败' : '草稿创建失败') } }
function openRewrite(draft: ContentDraft) { activeDraft.value = draft; rewritePlatforms.value = ['website']; rewriteMode.value = 'deterministic'; rewriteVariants.value = []; rewriteDialog.value = true }
async function rewriteDraft() { if (!activeDraft.value || !rewritePlatforms.value.length) return ElMessage.warning('请选择至少一个平台'); rewriting.value = true; try { const result = await contentApi.rewriteDraft(activeDraft.value.id, rewritePlatforms.value, rewriteMode.value); activeDraft.value = result; const key = rewriteMode.value === 'model' ? 'platform_model_variants' : 'platform_variants'; const rawVariants = (result.metadata[key] || {}) as Record<string, string | { content?: string }>; rewriteVariants.value = Object.entries(rawVariants).map(([platform, value]) => ({ platform, body: typeof value === 'string' ? value : value.content || '' })); ElMessage.success(rewriteMode.value === 'model' ? '模型改写已生成，请人工审核' : '多平台改写已生成') } catch (error) { showActionError(error, '内容改写失败') } finally { rewriting.value = false } }
function platformLabel(platform: string) { return ({ manual: '人工发布', douyin: '抖音', wechat: '公众号', x: 'X / 短帖', zhihu: '知乎', website: '网站' }[platform] || platform) }
function credentialStatusLabel(status: string) { return ({ active: '已启用', revoked: '已撤销', deleted: '已删除' }[status] || status || '未知') }
function openEdit(draft: ContentDraft) { editingDraft.value = draft; draftForm.value = { topic_id: draft.topic_id || '', title: draft.title, body: draft.body }; draftDialog.value = true }
function openCreate() { editingDraft.value = null; draftForm.value = { topic_id: '', title: '', body: '' }; draftDialog.value = true }
async function review(draft: ContentDraft, status: 'approved' | 'rejected') { try { await contentApi.reviewDraft(draft.id, status); ElMessage.success(status === 'approved' ? '草稿已通过' : '草稿已驳回'); await load() } catch (error) { showActionError(error, '草稿审核失败') } }
function openPublish(draft: ContentDraft) { activeDraft.value = draft; publishForm.value = { platform: 'manual', credential_id: '', externalId: '' }; publishDialog.value = true }
function exportDraft(draft: ContentDraft, format: 'markdown' | 'json') {
  const safeName = draft.title.trim().replace(/[\\/:*?"<>|\s]+/g, '-').slice(0, 80) || 'content-draft'
  const evidence = Array.isArray(draft.metadata?.evidence) ? draft.metadata.evidence : []
  const content = format === 'markdown'
    ? `# ${draft.title}\n\n> 审核状态：${reviewLabel(draft.review_status)}\n> 更新时间：${new Date(draft.updated_at).toLocaleString('zh-CN')}\n\n${draft.body}\n\n---\n\n## 发布信息\n\n- 选题 ID：${draft.topic_id || '未绑定'}\n- 草稿 ID：${draft.id}\n- 证据条目：${evidence.length}\n`
    : JSON.stringify({ exported_at: new Date().toISOString(), draft }, null, 2)
  const blob = new Blob([content], { type: format === 'markdown' ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${safeName}.${format === 'markdown' ? 'md' : 'json'}`
  anchor.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${format === 'markdown' ? 'Markdown' : 'JSON'} 发布包`)
}
async function copyDraft(draft: ContentDraft) {
  try {
    await navigator.clipboard.writeText(draft.body)
    ElMessage.success('正文已复制到剪贴板')
  } catch {
    ElMessage.warning('浏览器未允许访问剪贴板，请使用导出文件')
  }
}
async function publish() { if (!activeDraft.value || !publishForm.value.platform) return ElMessage.warning('请选择发布平台'); if (connectorRequiresCredentials(publishForm.value.platform) && !publishForm.value.credential_id) return ElMessage.warning('请先选择发布凭据'); publishing.value = true; try { await contentApi.publishDraft(activeDraft.value.id, publishForm.value.platform, publishForm.value.externalId.trim() || undefined, publishForm.value.credential_id || undefined); publishDialog.value = false; ElMessage.success('发布记录已保存'); await load() } catch (error) { showActionError(error, '内容发布失败') } finally { publishing.value = false } }
function openSchedule(draft: ContentDraft) { activeDraft.value = draft; scheduleForm.value = { platform: '', credential_id: '', scheduled_at: '' }; scheduleDialog.value = true }
async function schedule() {
  if (!activeDraft.value || !scheduleForm.value.platform || !scheduleForm.value.scheduled_at) return ElMessage.warning('请填写平台和未来排期时间')
  if (connectorRequiresCredentials(scheduleForm.value.platform) && !scheduleForm.value.credential_id) return ElMessage.warning('请先选择发布凭据')
  const scheduledAt = new Date(scheduleForm.value.scheduled_at)
  if (Number.isNaN(scheduledAt.getTime()) || scheduledAt.getTime() <= Date.now()) return ElMessage.warning('排期时间必须晚于当前时间')
  try {
    await contentApi.scheduleDraft(activeDraft.value.id, scheduleForm.value.platform, scheduledAt.toISOString(), scheduleForm.value.credential_id || undefined)
    scheduleDialog.value = false
    ElMessage.success('内容已加入发布日历')
    await load()
  } catch (error) { showActionError(error, '内容排期失败') }
}
function openConfirmPublish(record: ContentPublishRecord) { activePublish.value = record; confirmExternalId.value = ''; confirmDialog.value = true }
async function confirmPublish() { if (!activePublish.value) return; confirming.value = true; try { await contentApi.confirmPublish(activePublish.value.id, confirmExternalId.value.trim() || undefined); confirmDialog.value = false; ElMessage.success('发布状态已确认'); await load() } catch (error) { showActionError(error, '发布状态确认失败') } finally { confirming.value = false } }
function publishStatusLabel(status: string) { return ({ ready: '待确认', scheduled: '已排期', published: '已发布', failed: '失败' } as Record<string, string>)[status] || status }
function publishStatusType(status: string) { return status === 'published' ? 'success' : status === 'failed' ? 'danger' : status === 'ready' ? 'warning' : 'info' }
async function openRetrospective(record: ContentPublishRecord) { try { retrospective.value = await contentApi.createRetrospective(record.id); retrospectiveDialog.value = true } catch (error) { showActionError(error, '复盘生成失败') } }
function openMetric(record: ContentPublishRecord) { activePublish.value = record; metricForm.value = { impressions: 0, clicks: 0, likes: 0, comments: 0, shares: 0 }; metricDialog.value = true }
async function saveMetric() { if (!activePublish.value) return; try { await contentApi.addMetric(activePublish.value.id, metricForm.value); metricDialog.value = false; ElMessage.success('内容指标已保存'); await load() } catch (error) { showActionError(error, '内容指标保存失败') } }
async function importMetrics() {
  if (!workspaceId.value || !metricImportJson.value.trim()) return ElMessage.warning('请粘贴指标 JSON')
  let raw: unknown
  try { raw = JSON.parse(metricImportJson.value) } catch { return ElMessage.error('指标 JSON 格式无效') }
  const items = Array.isArray(raw) ? raw : (raw as { items?: unknown })?.items
  if (!Array.isArray(items)) return ElMessage.error('指标 JSON 必须是数组或包含 items 数组')
  try {
    const result = await contentApi.importMetrics({
      workspace_id: workspaceId.value,
      items: items as Array<{ publish_id: string; collected_at: string; metric: Record<string, unknown> }>,
    })
    metricImportDialog.value = false
    metricImportJson.value = ''
    ElMessage.success(`指标导入完成：新增 ${result.inserted} 条，跳过 ${result.skipped} 条`)
    await load()
  } catch (error) { showActionError(error, '指标导入失败') }
}
async function createCredential() { if (!workspaceId.value || !credentialForm.value.platform.trim() || !credentialForm.value.name.trim() || !credentialForm.value.json.trim()) return ElMessage.warning('请完整填写平台、名称和凭据 JSON'); let parsed: Record<string, string>; try { parsed = JSON.parse(credentialForm.value.json) } catch { return ElMessage.error('凭据 JSON 格式无效') } try { await contentApi.createCredential({ workspace_id: workspaceId.value, platform: credentialForm.value.platform.trim().toLowerCase(), name: credentialForm.value.name.trim(), credential_hint: credentialForm.value.hint.trim() || undefined, credentials: parsed }); credentialDialog.value = false; credentialForm.value = { platform: '', name: '', hint: '', json: '' }; ElMessage.success('凭据已加密保存'); await load() } catch (error) { showActionError(error, '凭据保存失败') } }
async function testCredential(credential: ContentCredential) { if (!workspaceId.value) return; testingCredentialId.value = credential.id; try { const result = await contentApi.testCredential(credential.id, workspaceId.value); if (result.status === 'not_supported') ElMessage.warning(result.message); else ElMessage.success(result.message) } catch (error) { showActionError(error, '连接测试失败') } finally { testingCredentialId.value = '' } }
async function revokeCredential(credential: ContentCredential) { try { await ElMessageBox.confirm(`确认撤销“${credential.name}”吗？已排期任务将无法使用它。`, '撤销凭据', { type: 'warning' }); await contentApi.revokeCredential(credential.id); ElMessage.success('凭据已撤销'); await load() } catch { /* 用户取消 */ } }
function reviewLabel(status: string) { return ({ pending: '待审核', approved: '已通过', rejected: '已驳回' }[status] || status) }
onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); workspaceId.value = workspaceStore.currentWorkspaceId || ''; await load() })
</script>

<style scoped lang="scss">
.content-home { max-width: 1440px; margin: 0 auto; }
.form-hint { display: block; margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.header-actions { display: flex; gap: 10px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: clamp(30px, 4vw, 46px); letter-spacing: -.04em; }
.subtitle { margin: 10px 0 0; color: var(--el-text-color-secondary); line-height: 1.7; }
.content-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 0 0 20px; }
.summary-card { display: flex; min-height: 108px; flex-direction: column; justify-content: space-between; padding: 16px 18px; border: 1px solid rgba(112, 74, 198, .13); border-radius: 16px; background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(249,247,255,.92)); box-shadow: 0 12px 30px rgba(79, 51, 133, .05); }
.summary-card span, .summary-card small { color: var(--el-text-color-secondary); font-size: 12px; }
.summary-card strong { color: #2c2140; font-family: Georgia, 'Times New Roman', serif; font-size: 30px; letter-spacing: -.04em; }
.summary-card.warm { background: linear-gradient(145deg, #fffaf0, #fff); }.summary-card.warm strong { color: #b4771c; }
.summary-card.green { background: linear-gradient(145deg, #f2fbf6, #fff); }.summary-card.green strong { color: #2f8a61; }
.summary-card.accent { background: linear-gradient(145deg, #eee6ff, #fff); }.summary-card.accent strong { color: var(--el-color-primary); }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.content-grid > .el-card, .calendar-card, .credentials-card { border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; box-shadow: 0 12px 30px rgba(79, 51, 133, .05); }
.calendar-card, .credentials-card { margin-top: 18px; }
.section-header { display: flex; justify-content: space-between; align-items: center; }
.credential-form { margin-top: 18px; }.dialog-note { margin-bottom: 18px; border-radius: 12px; }
.topic-row, .draft-row { display: flex; justify-content: space-between; gap: 16px; padding: 16px 0; border-bottom: 1px solid rgba(112, 74, 198, .1); }
.topic-row:last-child, .draft-row:last-child { border-bottom: 0; }
.topic-row p, .draft-row p { margin: 7px 0 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.actions { margin-top: 8px; }.rewrite-results { display: grid; gap: 12px; max-height: 48vh; overflow: auto; }
.rewrite-results pre { white-space: pre-wrap; word-break: break-word; line-height: 1.6; }
@media (max-width: 980px) { .content-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .page-header { display: block; }.header-actions { margin-top: 16px; }.content-grid, .content-summary { grid-template-columns: 1fr; } }
</style>
