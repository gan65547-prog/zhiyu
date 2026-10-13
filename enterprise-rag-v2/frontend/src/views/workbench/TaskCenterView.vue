<template>
  <section class="task-center">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / 任务中心
        </p>
        <h1>待处理任务</h1>
        <p class="subtitle">
          集中查看素材处理、知识审核、Agent 审批和内容审核，不跨域修改业务状态。
        </p>
      </div>
      <el-button
        :loading="loading"
        @click="loadTasks"
      >
        刷新
      </el-button>
    </header>
    <el-alert
      v-if="!workspaceId"
      type="warning"
      :closable="false"
    >
      请先选择工作空间。
    </el-alert>
    <el-card
      v-else
      shadow="never"
      class="task-card"
    >
      <el-table
        v-loading="loading"
        :data="tasks"
        empty-text="暂无待处理任务"
      >
        <el-table-column
          prop="title"
          label="任务"
          min-width="300"
        />
        <el-table-column
          prop="kind"
          label="类型"
          width="150"
        >
          <template #default="scope">
            {{ kindLabel(scope.row.kind) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          label="状态"
          width="140"
        />
        <el-table-column
          prop="priority"
          label="优先级"
          width="100"
        >
          <template #default="scope">
            <el-tag :type="scope.row.priority > 1 ? 'danger' : 'info'">
              {{ scope.row.priority > 1 ? '高' : '普通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="120"
          fixed="right"
        >
          <template #default="scope">
            <el-button
              type="primary"
              link
              @click="router.push(scope.row.route)"
            >
              去处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workbenchApi, type WorkbenchTask } from '@/api/workbench'
import { useWorkspaceStore } from '@/stores/workspace'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const tasks = ref<WorkbenchTask[]>([])
const loading = ref(false)

async function loadTasks() {
  if (!workspaceId.value) return
  loading.value = true
  try { tasks.value = (await workbenchApi.listTasks(workspaceId.value)).items || [] } finally { loading.value = false }
}
function kindLabel(kind: string) { return ({ asset: '素材处理', knowledge_review: '知识审核', agent_approval: 'Agent 审批', content_review: '内容审核', content_publish: '内容发布', agent_run: 'Agent 运行', research_run: '研究运行' }[kind] || kind) }
onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); await loadTasks() })
</script>

<style scoped lang="scss">
.task-center { max-width: 1440px; margin: 0 auto; padding-bottom: 32px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: #704ac6; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h1 { margin: 0; color: #241d2e; font-size: 32px; letter-spacing: -0.04em; }
.subtitle { margin: 10px 0 0; color: #827a90; line-height: 1.7; }
.task-card { border: 1px solid rgba(124, 77, 200, 0.14); border-radius: 18px; background: rgba(255, 255, 255, 0.86); box-shadow: 0 18px 40px rgba(62, 42, 108, 0.07); backdrop-filter: blur(10px); }
:deep(.el-table th.el-table__cell) { background: #faf8ff; color: #6d6378; }
:deep(.el-table tr:hover > td.el-table__cell) { background: #fbf9ff; }
</style>
