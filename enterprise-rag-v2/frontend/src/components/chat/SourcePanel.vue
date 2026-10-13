<template>
  <div class="source-panel">
    <div
      v-for="source in sources"
      :key="source.segment_id"
      class="source-item"
    >
      <div class="source-header">
        <el-icon><Document /></el-icon>
        <span class="doc-name">{{ source.document_name }}</span>
        <span class="score">相似度: {{ (source.score * 100).toFixed(1) }}%</span>
      </div>
      <div class="source-content">
        {{ source.content }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import type { Source } from '@/types'

defineProps<{
  sources: Source[]
}>()
</script>

<style scoped lang="scss">
.source-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;

  .source-item {
    background: #fff;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;

    .source-header {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
      color: #606266;

      .doc-name {
        flex: 1;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .score {
        font-size: 12px;
        color: #67c23a;
      }
    }

    .source-content {
      color: #606266;
      line-height: 1.6;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
    }
  }
}
</style>
