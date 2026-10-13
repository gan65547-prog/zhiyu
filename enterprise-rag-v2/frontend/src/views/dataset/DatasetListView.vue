<template>
  <div class="dataset-list-view">
    <div class="header">
      <div>
        <p class="eyebrow">KNOWLEDGE LIBRARY · CURRENT WORKSPACE</p>
        <h1>知识库</h1>
        <p class="subtitle">把文档、经验和研究材料组织成可以持续检索与复用的上下文。</p>
      </div>
      <div class="header-actions">
        <div class="header-stats">
          <span><strong>{{ datasetStore.total }}</strong> 个知识库</span>
          <span><strong>{{ totalDocuments }}</strong> 份文档</span>
        </div>
        <el-button
          v-if="canCreateDataset"
          type="primary"
          size="large"
          @click="router.push('/datasets/create')"
        >
          <el-icon><Plus /></el-icon>
          新建知识库
        </el-button>
      </div>
    </div>

    <div
      v-if="datasetStore.loading"
      class="loading"
    >
      <LoadingSpinner text="加载中..." />
    </div>

    <div
      v-else-if="!workspaceStore.hasWorkspaces"
      class="empty"
    >
      <el-empty description="暂无工作空间，请先创建工作空间">
        <el-button
          v-if="canCreateWorkspace"
          type="primary"
          @click="router.push('/workspaces')"
        >
          去创建工作空间
        </el-button>
      </el-empty>
    </div>

    <div
      v-else-if="datasetStore.datasets.length === 0"
      class="empty"
    >
      <el-empty description="暂无知识库">
        <el-button
          v-if="canCreateDataset"
          type="primary"
          @click="router.push('/datasets/create')"
        >
          新建知识库
        </el-button>
      </el-empty>
    </div>

    <el-row
      v-else
      :gutter="20"
    >
      <el-col
        v-for="dataset in datasetStore.datasets"
        :key="dataset.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <el-card
          class="dataset-card"
          shadow="hover"
          @click="goToDetail(dataset)"
        >
          <div class="card-header">
            <span class="dataset-mark">
              <Collection />
            </span>
            <el-dropdown 
              v-if="canEditDataset || canDeleteDataset" 
              trigger="click" 
              @command="(cmd: string) => handleCommand(cmd, dataset)" 
              @click.stop
            >
              <el-icon
                class="more-icon"
                @click.stop
              >
                <More />
              </el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-if="canEditDataset"
                    command="edit"
                  >
                    编辑
                  </el-dropdown-item>
                  <el-dropdown-item command="documents">
                    文档管理
                  </el-dropdown-item>
                  <el-dropdown-item command="chat">
                    开始问答
                  </el-dropdown-item>
                  <el-dropdown-item
                    v-if="canDeleteDataset"
                    command="delete"
                    divided
                  >
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <h3>{{ dataset.name }}</h3>
          <el-tag size="small" effect="plain" :type="dataset.document_count ? 'success' : 'info'">
            {{ dataset.document_count ? '可检索' : '待导入' }}
          </el-tag>
          <p class="description">
            {{ dataset.description || '暂无描述' }}
          </p>
          <div class="meta">
            <span>{{ dataset.document_count }} 个文档</span>
            <span>{{ formatDate(dataset.created_at) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div
      v-if="datasetStore.total > datasetStore.pageSize"
      class="pagination"
    >
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="datasetStore.pageSize"
        :total="datasetStore.total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import { useWorkspaceStore } from '@/stores/workspace'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Plus, Collection, More } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'
import { usePermission } from '@/composables/usePermission'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import type { Dataset } from '@/types'

const router = useRouter()
const datasetStore = useDatasetStore()
const workspaceStore = useWorkspaceStore()
const { canCreateDataset, canEditDataset, canDeleteDataset, canCreateWorkspace } = usePermission()
const currentPage = ref(1)
const totalDocuments = computed(() => datasetStore.datasets.reduce((sum, item) => sum + Number(item.document_count || 0), 0))

onMounted(async () => {
  console.log('DatasetListView onMounted: loading datasets')
  await workspaceStore.fetchWorkspaces()
  if (workspaceStore.hasWorkspaces) {
    datasetStore.fetchDatasets()
  } else {
    datasetStore.datasets = []
  }
})

// 当组件重新激活时重新加载数据
onActivated(async () => {
  console.log('DatasetListView onActivated: reloading datasets')
  await workspaceStore.fetchWorkspaces()
  if (workspaceStore.hasWorkspaces) {
    datasetStore.fetchDatasets()
  } else {
    datasetStore.datasets = []
  }
})

const goToDetail = (dataset: Dataset) => {
  router.push(`/datasets/${dataset.id}`)
}

const handleCommand = async (command: string, dataset: Dataset) => {
  switch (command) {
    case 'edit':
      router.push(`/datasets/${dataset.id}`)
      break
    case 'documents':
      router.push(`/datasets/${dataset.id}`)
      break
    case 'chat':
      router.push(`/chat/${dataset.id}`)
      break
    case 'delete':
      await ElMessageBox.confirm('确定删除该知识库吗？此操作将删除所有关联文档。', '提示', {
        type: 'warning'
      })
      await datasetStore.deleteDataset(dataset.id)
      ElMessage.success('删除成功')
      break
  }
}

const handlePageChange = (page: number) => {
  datasetStore.fetchDatasets({ page })
}
</script>

<style scoped lang="scss">
@use '@/styles/tokens/colors' as *;
@use '@/styles/tokens/spacing' as *;
@use '@/styles/tokens/radius' as *;
@use '@/styles/tokens/shadows' as *;
@use '@/styles/tokens/transitions' as *;

.dataset-list-view {
  --card-bg: rgba(255, 255, 255, 0.9);
  --card-border: rgba(148, 163, 184, 0.2);

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 28px;
    padding: 6px 0 20px;
    border-bottom: 1px solid rgba(112, 74, 198, 0.11);

    .eyebrow {
      margin: 0 0 8px;
      color: #8062bd;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .17em;
    }

    .subtitle {
      max-width: 560px;
      margin: 9px 0 0;
      color: #81778f;
      font-size: 14px;
      line-height: 1.6;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .header-stats {
      display: flex;
      gap: 16px;
      color: #8e849b;
      font-size: 12px;

      span {
        display: flex;
        align-items: baseline;
        gap: 5px;
        white-space: nowrap;
      }

      strong {
        color: #302342;
        font-size: 22px;
        letter-spacing: -.05em;
      }
    }

    h1 {
      margin: 0;
      color: #21172f;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(34px, 4vw, 48px);
      font-weight: 700;
      letter-spacing: -.055em;
    }

    .el-button--primary {
      border: none;
      border-radius: 12px;
      background: linear-gradient(135deg, #704ac6, #8b62d9);
      box-shadow: 0 10px 20px rgba(112, 74, 198, 0.2);
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: var(--el-box-shadow-dark, #{$shadow-md});
      }
    }
  }

  .loading,
  .empty {
    padding: 60px 0;
    min-height: 400px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .dataset-card {
    margin-bottom: $spacing-5;
    cursor: pointer;
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    height: 100%;
    border-radius: 18px;
    border: 1px solid rgba(112, 74, 198, .12);
    background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(250,247,255,.78));
    backdrop-filter: blur(8px);

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 16px 30px rgba(79, 51, 133, 0.12);
      border-color: rgba(112, 74, 198, 0.35);
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: $spacing-3;

      .more-icon {
        cursor: pointer;
        opacity: 0.6;
        padding: $spacing-1;
        border-radius: $radius-sm;
        transition: all 0.2s ease;
        color: var(--el-text-color-secondary, #{$color-text-tertiary});

        &:hover {
          opacity: 1;
          background-color: rgba(112, 74, 198, 0.1);
          color: var(--el-text-color-primary, #{$color-text-primary});
        }
      }
    }

    .dataset-mark {
      display: grid;
      width: 44px;
      height: 44px;
      place-items: center;
      color: #704ac6;
      border: 1px solid rgba(112, 74, 198, .16);
      border-radius: 14px;
      background: linear-gradient(145deg, #f1eaff, #fff);
      font-size: 22px;
      box-shadow: 0 7px 16px rgba(112, 74, 198, .08);
    }

    h3 {
      margin: 0 0 $spacing-2;
      font-size: $font-size-lg;
      font-weight: $font-weight-semibold;
      color: var(--el-text-color-primary, #{$color-text-primary});
      line-height: 1.3;
    }

    .el-tag {
      margin: -2px 0 8px;
      border-radius: 999px;
    }

    .description {
      color: var(--el-text-color-secondary, #{$color-text-tertiary});
      font-size: $font-size-sm;
      margin-bottom: $spacing-3;
      min-height: 40px;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      line-height: 1.5;
    }

    .meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--el-text-color-placeholder, #{$color-text-disabled});
      font-size: $font-size-xs;
      padding-top: $spacing-2;
      border-top: 1px solid var(--el-border-color-extra-light, #fafafa);

      span {
        display: flex;
        align-items: center;
        gap: 4px;

        &::before {
          content: '';
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background-color: #9b7bdd;
        }

        &:last-child::before {
          background-color: transparent;
          content: '📅';
          font-size: 10px;
        }
      }
    }
  }

  .pagination {
    margin-top: $spacing-8;
    display: flex;
    justify-content: center;
    padding: $spacing-4 0;
  }

  // Responsive adjustments
  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      gap: $spacing-4;
      text-align: center;

      h1 {
        justify-content: center;
      }
    }

    .dataset-card {
      margin-bottom: $spacing-4;
    }
  }
}

// Dark mode specific styles
html.dark {
  .dataset-list-view {
    --card-bg: rgba(30, 41, 59, 0.72);
    --card-border: rgba(148, 163, 184, 0.2);

    .header {
      border-bottom-color: rgba(148, 163, 184, 0.2);

      h1 {
        color: var(--el-text-color-primary);
      }
    }

    .dataset-card {
      &:hover {
        border-color: rgba(100, 181, 246, 0.4);
        box-shadow: 0 16px 30px rgba(2, 6, 23, 0.42);
      }

      .card-header {
        .more-icon {
          &:hover {
            background-color: var(--el-fill-color-dark);
          }
        }
      }

      h3 {
        color: var(--el-text-color-primary);
      }

      .description {
        color: var(--el-text-color-secondary);
      }

      .meta {
        border-top-color: var(--el-border-color);
        color: var(--el-text-color-placeholder);

        span:first-child::before {
          background-color: rgba(172, 143, 232, 0.7);
        }
      }
    }
  }
}
</style>
