<template>
  <div class="conversation-history">
    <div class="history-header">
      <h3>对话历史</h3>
      <button
        class="btn-new-chat"
        @click="handleNewChat"
      >
        <i class="pi pi-plus" />
        新对话
      </button>
    </div>

    <div class="search-box">
      <el-input
        v-model="searchQuery"
        placeholder="搜索对话..."
        class="w-full"
        @input="handleSearch"
      />
    </div>

    <div class="conversation-list">
      <div
        v-for="conversation in filteredConversations"
        :key="conversation.id"
        class="conversation-item"
        :class="{ active: conversation.id === activeConversationId }"
        @click="handleSelect(conversation.id)"
      >
        <div class="conversation-icon">
          <i class="pi pi-comments" />
        </div>
        <div class="conversation-info">
          <span class="conversation-title">{{ conversation.title || '新对话' }}</span>
          <span class="conversation-time">{{ formatTime(conversation.updated_at) }}</span>
        </div>
        <div class="conversation-actions">
          <button
            class="btn-action"
            @click.stop="handleDelete(conversation.id)"
          >
            <i class="pi pi-trash" />
          </button>
        </div>
      </div>

      <div
        v-if="loading"
        class="loading-state"
      >
        <i class="pi pi-spinner pi-spin" />
        <span>加载中...</span>
      </div>

      <div
        v-else-if="filteredConversations.length === 0"
        class="empty-state"
      >
        <i class="pi pi-inbox" />
        <span>暂无对话历史</span>
      </div>
    </div>

    <div class="history-footer">
      <button
        class="btn-clear"
        @click="handleClearAll"
      >
        <i class="pi pi-trash" />
        清空历史
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { conversationApi } from '@/api/conversation'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'

interface Props {
  activeConversationId?: string | null
  datasetId?: string | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [conversationId: string]
  new: []
}>()

const conversations = ref<any[]>([])
const loading = ref(false)
const searchQuery = ref('')

const filteredConversations = computed(() => {
  if (!searchQuery.value) return conversations.value
  const query = searchQuery.value.toLowerCase()
  return conversations.value.filter(c => 
    c.title?.toLowerCase().includes(query)
  )
})

onMounted(async () => {
  await fetchConversations()
})

watch(() => props.datasetId, () => {
  fetchConversations()
})

async function fetchConversations() {
  loading.value = true
  try {
    const response = await conversationApi.list({ dataset_id: props.datasetId || undefined, page: 1, page_size: 50 })
    conversations.value = (response as any).items || (response as any).data?.items || []
  } catch (error: any) {
    ElMessage.error(error.message || '加载对话历史失败')
  } finally {
    loading.value = false
  }
}

function formatTime(dateStr: string) {
  try {
    return formatDistanceToNow(new Date(dateStr), {
      addSuffix: true,
      locale: zhCN
    })
  } catch {
    return ''
  }
}

function handleSelect(conversationId: string) {
  emit('select', conversationId)
}

function handleNewChat() {
  emit('new')
}

async function handleDelete(conversationId: string) {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '删除确认', { type: 'warning' })
    await conversationApi.delete(conversationId)
    conversations.value = conversations.value.filter(c => c.id !== conversationId)
    ElMessage.success('对话已删除')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message || '删除对话失败')
  }
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm('确定要清空所有对话历史吗？此操作不可恢复。', '清空确认', { type: 'warning' })
    for (const conversation of conversations.value) await conversationApi.delete(conversation.id)
    conversations.value = []
    ElMessage.success('对话历史已清空')
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message || '清空对话历史失败')
  }
}

function handleSearch() {
  // 搜索逻辑已通过 computed 实现
}

defineExpose({
  refresh: fetchConversations
})
</script>

<style scoped>
.conversation-history {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-card);
  border-right: 1px solid var(--surface-border);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--surface-border);
}

.history-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.btn-new-chat {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  background: var(--primary-color);
  color: white;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-new-chat:hover {
  background: var(--primary-color-dark);
}

.search-box {
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-border);
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 4px;
}

.conversation-item:hover {
  background-color: var(--surface-hover);
}

.conversation-item.active {
  background-color: var(--primary-color-lightest);
}

.conversation-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--surface-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-color-secondary);
}

.conversation-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.conversation-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-time {
  font-size: 12px;
  color: var(--text-color-secondary);
}

.conversation-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.conversation-item:hover .conversation-actions {
  opacity: 1;
}

.btn-action {
  padding: 6px;
  border: none;
  background: transparent;
  color: var(--text-color-secondary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-action:hover {
  background: var(--surface-200);
  color: var(--red-500);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--text-color-secondary);
}

.history-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--surface-border);
}

.btn-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--surface-border);
  background: transparent;
  color: var(--text-color-secondary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear:hover {
  background: var(--red-50);
  border-color: var(--red-200);
  color: var(--red-500);
}
</style>
