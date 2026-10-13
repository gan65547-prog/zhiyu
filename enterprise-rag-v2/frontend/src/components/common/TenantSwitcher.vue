<template>
  <div
    v-if="authStore.isSuperuser"
    class="tenant-switcher"
  >
    <el-select
      v-model="currentTenantId"
      placeholder="选择租户"
      filterable
      size="default"
      @change="handleTenantChange"
    >
      <el-option
        v-for="tenant in tenantList"
        :key="tenant.id"
        :label="tenant.name"
        :value="tenant.id"
      >
        <div class="tenant-option">
          <span class="tenant-name">{{ tenant.name }}</span>
        </div>
      </el-option>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getTenantList, type Tenant } from '@/api/tenant'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()
const currentTenantId = ref('')
const tenantList = ref<Tenant[]>([])

onMounted(async () => {
  if (authStore.isSuperuser) {
    await loadTenants()
    currentTenantId.value = authStore.tenantId || ''
  }
})

const loadTenants = async () => {
  try {
    const response: any = await getTenantList()
    tenantList.value = response.data || []
  } catch (error: any) {
    console.error('加载租户列表失败:', error)
    ElMessage.error('加载租户列表失败')
  }
}

const handleTenantChange = async (tenantId: string) => {
  const previousTenantId = authStore.tenantId || ''
  if (!tenantId || tenantId === previousTenantId) return
  try {
    await authStore.switchTenantContext(tenantId)
    ElMessage.success('租户上下文已切换')
    await router.push('/')
  } catch (error: any) {
    currentTenantId.value = previousTenantId
    ElMessage.error(error?.response?.data?.detail || '租户上下文切换失败，已保留当前视图')
  }
}

</script>

<style scoped>
.tenant-switcher {
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.tenant-switcher :deep(.el-select) {
  width: 100%;
}

.tenant-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tenant-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>
