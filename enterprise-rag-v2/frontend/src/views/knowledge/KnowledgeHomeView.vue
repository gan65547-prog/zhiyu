<template>
  <section class="knowledge-home">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / 知识中心
        </p><h1>知识卡片</h1><p class="subtitle">
          把素材中的定义、结论和经验沉淀为可审核的团队知识。
        </p>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :disabled="!workspaceId"
          @click="openCreate"
        >
          <el-icon><Plus /></el-icon> 新建知识卡片
        </el-button>
        <el-button @click="$router.push('/knowledge/network')">关系网络</el-button>
      </div>
    </header>

    <el-alert
      class="notice"
      type="info"
      :closable="false"
      show-icon
    >
      只有绑定证据的卡片才能审核通过，确保每条关键结论都可回溯到原始素材。
    </el-alert>

    <div class="knowledge-summary">
      <div><span>当前卡片</span><strong>{{ items.length }}</strong><small>按当前筛选结果</small></div>
      <div><span>待审核</span><strong>{{ items.filter(item => item.review_status === 'draft').length }}</strong><small>需要人工核对</small></div>
      <div><span>已通过</span><strong>{{ items.filter(item => item.review_status === 'approved').length }}</strong><small>可进入关系网络</small></div>
      <div><span>证据总数</span><strong>{{ items.reduce((sum, item) => sum + (item.evidence?.length || 0), 0) }}</strong><small>可回溯原始素材</small></div>
    </div>

    <div class="toolbar">
      <el-radio-group
        v-model="filter"
        @change="loadItems"
      >
        <el-radio-button value="">
          全部
        </el-radio-button><el-radio-button value="draft">
          待审核
        </el-radio-button><el-radio-button value="approved">
          已通过
        </el-radio-button><el-radio-button value="rejected">
          已驳回
        </el-radio-button>
      </el-radio-group>
      <el-button
        text
        :loading="loading"
        @click="loadItems"
      >
        刷新
      </el-button>
    </div>

    <div
      v-if="items.length"
      class="card-grid"
    >
      <el-card
        v-for="item in items"
        :key="item.id"
        shadow="never"
        class="knowledge-card"
        :class="{ 'target-knowledge-card': item.id === targetItemId }"
      >
        <div class="card-title">
          <div>
            <el-tag size="small">
              {{ itemTypeLabel(item.item_type) }}
            </el-tag><h3>{{ item.title }}</h3>
          </div><el-tag :type="reviewType(item.review_status)">
            {{ reviewLabel(item.review_status) }}
          </el-tag>
        </div>
        <p class="definition">
          {{ item.definition || '暂无定义' }}
        </p>
        <div
          v-if="item.conclusions?.length"
          class="conclusions"
        >
          <strong>关键结论</strong><ul>
            <li
              v-for="conclusion in item.conclusions"
              :key="conclusion"
            >
              {{ conclusion }}
            </li>
          </ul>
        </div>
        <div class="evidence">
          <el-icon><Document /></el-icon><span>{{ item.evidence.length }} 条证据</span><span>置信度 {{ Math.round(item.confidence * 100) }}%</span>
        </div>
        <div
          v-if="item.review_status !== 'approved'"
          class="card-actions"
        >
          <el-button
            size="small"
            type="success"
            :disabled="!item.evidence.length"
            @click="review(item, 'approved')"
          >
            审核通过
          </el-button><el-button
            size="small"
            @click="review(item, 'rejected')"
          >
            驳回
          </el-button>
        </div>
        <div class="card-actions secondary-actions">
          <el-button size="small" text @click="startEdit(item)">
            编辑
          </el-button>
          <el-button size="small" text @click="showVersions(item)">
            查看版本
          </el-button>
        </div>
      </el-card>
    </div>
    <el-empty
      v-else
      :description="loading ? '加载中...' : '暂无知识卡片'"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="editId ? '编辑知识卡片' : '新建知识卡片'"
      width="600px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item
          label="标题"
          :required="!editId"
        >
          <el-input
            v-model="form.title"
            placeholder="例如：客户采购决策的三个关键因素"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.item_type">
            <el-option
              v-for="type in itemTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          label="一句话定义"
          required
        >
          <el-input
            v-model="form.definition"
            type="textarea"
            :rows="3"
            placeholder="用一句话说明这条知识"
          />
        </el-form-item>
        <el-form-item label="关键结论（每行一条）">
          <el-input
            v-model="form.conclusions"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
        <el-form-item
          label="关联素材"
          required
        >
          <el-select
            v-model="form.asset_id"
            clearable
            :disabled="Boolean(editId)"
            placeholder="选择作为证据的素材"
          >
            <el-option
              v-for="asset in assets"
              :key="asset.id"
              :label="asset.title"
              :value="asset.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          label="证据摘录"
          :required="!editId"
        >
          <el-input
            v-model="form.quote"
            type="textarea"
            :rows="4"
            placeholder="粘贴支持这条知识的原文摘录"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button><el-button
          type="primary"
          :loading="submitting"
          @click="saveItem"
        >
          保存并提交审核
        </el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="versionsVisible" title="知识卡片版本" width="620px">
      <el-empty v-if="!versions.length" description="暂无版本记录" />
      <el-radio-group v-else v-model="selectedVersionId">
        <el-radio
          v-for="version in versions"
          :key="version.id"
          :value="version.id"
          class="version-option"
        >
          v{{ version.version }} · {{ version.title }} · {{ formatDate(version.created_at) }}
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="versionsVisible = false">关闭</el-button>
        <el-button type="warning" :disabled="!selectedVersionId" @click="rollbackSelected">回滚并重新审核</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Plus } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api/knowledge'
import { assetApi } from '@/api/asset'
import type { Asset } from '@/types/asset'
import type { KnowledgeItem, KnowledgeItemVersion, KnowledgeReviewStatus } from '@/types/knowledge'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const route = useRoute()
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const items = ref<KnowledgeItem[]>([])
const assets = ref<Asset[]>([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const versionsVisible = ref(false)
const editId = ref('')
const versions = ref<KnowledgeItemVersion[]>([])
const selectedVersionId = ref('')
const versionItemId = ref('')
const filter = ref<KnowledgeReviewStatus | ''>('')
const targetItemId = computed(() => String(route.query.item_id || ''))
const form = reactive({ title: '', item_type: 'concept', definition: '', conclusions: '', asset_id: '', quote: '' })
const itemTypes = [{ value: 'concept', label: '概念' }, { value: 'method', label: '方法' }, { value: 'case', label: '案例' }, { value: 'opinion', label: '观点' }, { value: 'conclusion', label: '结论' }]

async function loadItems() {
  if (!workspaceId.value) return
  loading.value = true
  try { items.value = (await knowledgeApi.list(workspaceId.value, filter.value || undefined)).items || [] } finally { loading.value = false }
}
async function loadAssets() { if (workspaceId.value) assets.value = (await assetApi.list(workspaceId.value, { status: 'ready', page: 1, page_size: 100 })).items || [] }
function resetForm() { Object.assign(form, { title: '', item_type: 'concept', definition: '', conclusions: '', asset_id: '', quote: '' }); editId.value = '' }
function openCreate() { resetForm(); dialogVisible.value = true }
function startEdit(item: KnowledgeItem) { editId.value = item.id; Object.assign(form, { title: item.title, item_type: item.item_type, definition: item.definition, conclusions: item.conclusions.join('\n'), asset_id: '', quote: '' }); dialogVisible.value = true }
async function saveItem() {
  if (!workspaceId.value || !form.title.trim() || !form.definition.trim()) return ElMessage.warning('请填写标题和定义')
  if (!editId.value && (!form.asset_id || !form.quote.trim())) return ElMessage.warning('新建卡片必须填写证据素材和摘录')
  submitting.value = true
  try {
    if (editId.value) {
      await knowledgeApi.update(editId.value, { title: form.title.trim(), item_type: form.item_type, definition: form.definition.trim(), conclusions: form.conclusions.split('\n').map(item => item.trim()).filter(Boolean) })
      ElMessage.success('知识卡片已更新，等待重新审核')
    } else {
      const item = await knowledgeApi.create({ workspace_id: workspaceId.value, title: form.title.trim(), item_type: form.item_type, definition: form.definition.trim(), conclusions: form.conclusions.split('\n').map(item => item.trim()).filter(Boolean) })
      await knowledgeApi.addEvidence(item.id, { asset_id: form.asset_id, quote: form.quote.trim() })
      ElMessage.success('知识卡片已提交审核')
    }
    resetForm()
    dialogVisible.value = false
    await loadItems()
  } finally { submitting.value = false }
}
async function showVersions(item: KnowledgeItem) { versionItemId.value = item.id; selectedVersionId.value = ''; versions.value = await knowledgeApi.versions(item.id); versionsVisible.value = true }
async function rollbackSelected() { if (!versionItemId.value || !selectedVersionId.value) return; await knowledgeApi.rollback(versionItemId.value, selectedVersionId.value); ElMessage.success('已回滚并进入待审核'); versionsVisible.value = false; await loadItems() }
async function review(item: KnowledgeItem, status: KnowledgeReviewStatus) { await knowledgeApi.review(item.id, status); ElMessage.success(status === 'approved' ? '知识卡片已通过' : '知识卡片已驳回'); await loadItems() }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN') }
function itemTypeLabel(type: string) { return itemTypes.find(item => item.value === type)?.label || type }
function reviewLabel(status: string) { return ({ draft: '待审核', approved: '已通过', rejected: '已驳回' }[status] || status) }
function reviewType(status: string) { return status === 'approved' ? 'success' : status === 'rejected' ? 'danger' : 'warning' }
onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); await Promise.all([loadItems(), loadAssets()]) })
</script>

<style scoped lang="scss">
.knowledge-home { max-width: 1440px; margin: 0 auto; }.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-weight: 600; }h1 { margin: 0; color: var(--el-text-color-primary); }.subtitle { margin: 8px 0 0; color: var(--el-text-color-secondary); }.toolbar { display: flex; justify-content: space-between; align-items: center; margin: 20px 0; }.card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }.knowledge-card { border: 1px solid var(--el-border-color-lighter); }.card-title { display: flex; justify-content: space-between; gap: 8px; }.card-title h3 { margin: 10px 0 0; color: var(--el-text-color-primary); }.definition { min-height: 48px; margin: 18px 0; color: var(--el-text-color-regular); line-height: 1.6; }.conclusions { padding: 10px 12px; background: var(--el-fill-color-lighter); border-radius: 8px; font-size: 13px; }.conclusions ul { margin: 8px 0 0; padding-left: 18px; }.evidence { display: flex; gap: 10px; margin-top: 16px; color: var(--el-text-color-secondary); font-size: 12px; }.card-actions { display: flex; justify-content: flex-end; margin-top: 14px; }.secondary-actions { margin-top: 0; }.version-option { display: block; margin: 12px 0; }.el-select { width: 100%; }@media (max-width: 900px) { .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }@media (max-width: 600px) { .page-header { display: block; }.page-header .el-button { margin-top: 16px; }.card-grid { grid-template-columns: 1fr; } }
.knowledge-home { max-width: 1440px; }
.page-header { gap: 24px; }
.header-actions { display: flex; gap: 10px; padding-top: 18px; }
.eyebrow { font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h1 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(32px, 4vw, 48px); letter-spacing: -.045em; }
.subtitle { max-width: 720px; line-height: 1.75; }
.notice { margin-bottom: 18px; border: 1px solid rgba(112,74,198,.14); border-radius: 14px; background: #faf8ff; }
.knowledge-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }
.knowledge-summary > div { display: flex; flex-direction: column; gap: 5px; padding: 17px 20px; border: 1px solid rgba(112,74,198,.13); border-radius: 18px; background: linear-gradient(145deg,rgba(255,255,255,.96),rgba(249,247,255,.9)); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
.knowledge-summary span, .knowledge-summary small { color: var(--el-text-color-secondary); }
.knowledge-summary strong { color: var(--el-color-primary); font-family: Georgia, 'Times New Roman', serif; font-size: 30px; }
.toolbar { padding: 12px 14px; margin: 18px 0; border: 1px solid rgba(112,74,198,.13); border-radius: 16px; background: rgba(255,255,255,.78); box-shadow: 0 8px 22px rgba(79,51,133,.04); }
.card-grid { gap: 18px; }
.knowledge-card { border: 1px solid rgba(112,74,198,.13); border-radius: 18px; background: linear-gradient(145deg,rgba(255,255,255,.97),rgba(249,247,255,.9)); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
.target-knowledge-card { outline: 2px solid var(--el-color-warning); outline-offset: 2px; }
.knowledge-card :deep(.el-card__body) { padding: 20px; }
.card-title h3 { font-size: 18px; letter-spacing: -.02em; }
.definition { color: var(--el-text-color-secondary); line-height: 1.75; }
.conclusions { border: 1px solid rgba(112,74,198,.09); border-radius: 12px; background: #faf8ff; }
.evidence { padding-top: 13px; border-top: 1px solid rgba(112,74,198,.09); color: var(--el-text-color-secondary); }
.card-actions { gap: 6px; }
.version-option { padding: 10px 12px; border: 1px solid rgba(112,74,198,.1); border-radius: 10px; }
@media (max-width: 900px) { .knowledge-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .header-actions { padding-top: 0; flex-wrap: wrap; } .knowledge-summary { grid-template-columns: 1fr 1fr; } }
</style>
