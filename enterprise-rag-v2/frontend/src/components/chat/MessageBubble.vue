<template>
  <div
    class="message-bubble"
    :class="message.role"
  >
    <div class="avatar">
      <el-avatar
        :size="40"
        :src="message.role === 'user' ? userAvatar : aiAvatar"
      />
    </div>
    <div class="content">
      <div
        class="bubble"
        v-html="renderedContent"
      />
      <div
        v-if="message.sources?.length"
        class="sources"
      >
        <div class="sources-title">
          参考来源：
        </div>
        <SourcePanel :sources="message.sources" />
      </div>
      <div class="time">
        {{ formatTime(message.created_at) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import SourcePanel from './SourcePanel.vue'
import type { Message } from '@/types'

const props = defineProps<{
  message: Message
}>()

const userAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'
const aiAvatar = '/ai-avatar.png'

const renderedContent = computed(() => {
  let content = props.message.content || ''
  // 脱敏处理：隐藏token
  content = content.replace(/(token|access_token|auth_token|api_key)\s*[:=]\s*['"]([a-zA-Z0-9_\-]+)['"]/gi, '$1: [REDACTED]')
  content = content.replace(/(Bearer|Token)\s+([a-zA-Z0-9_\-\.]+)/gi, '$1 [REDACTED]')
  return marked(content)
})

const formatTime = (date: string) => {
  if (!date) return ''
  return new Date(date).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped lang="scss">
.message-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;

  &.user {
    flex-direction: row-reverse;

    .content {
      align-items: flex-end;

      .bubble {
        background: linear-gradient(135deg, #704ac6, #8d61d6);
        color: #fff;

        :deep(code) {
          background: rgba(255, 255, 255, 0.2);
        }
      }
    }
  }

  .content {
    display: flex;
    flex-direction: column;
    max-width: 70%;

    .bubble {
      padding: 12px 16px;
      background: #faf8ff;
      border: 1px solid rgba(124, 77, 200, 0.14);
      border-radius: 16px;
      word-break: break-word;
      line-height: 1.6;

      :deep(p) {
        margin: 0 0 8px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      :deep(pre) {
        background: #282c34;
        padding: 12px;
        border-radius: 6px;
        overflow-x: auto;
        margin: 8px 0;

        code {
          color: #abb2bf;
          background: none;
          padding: 0;
        }
      }

      :deep(code) {
        background: #f0e8ff;
        color: #5d2cb6;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
      }

      :deep(ul),
      :deep(ol) {
        margin: 8px 0;
        padding-left: 20px;
      }
    }

    .sources {
      margin-top: 12px;
      max-width: 100%;

      .sources-title {
        font-size: 12px;
        color: #827a90;
        margin-bottom: 8px;
      }
    }

    .time {
      font-size: 12px;
      color: #a39aaa;
      margin-top: 4px;
    }
  }
}
</style>
