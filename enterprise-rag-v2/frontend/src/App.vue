<template>
  <el-result
    v-if="fatalError"
    icon="error"
    title="页面加载失败"
    sub-title="前端捕获到未恢复异常，请刷新页面后重试。"
  >
    <template #extra>
      <el-button type="primary" @click="reloadPage">刷新页面</el-button>
    </template>
  </el-result>
  <router-view v-else />
</template>

<script setup lang="ts">
import { onErrorCaptured, onMounted, ref } from 'vue'
import { useUserConfigStore } from './stores/userConfig'

const fatalError = ref<Error | null>(null)

onMounted(() => {
  const userConfigStore = useUserConfigStore()
  userConfigStore.init()
})

onErrorCaptured((error) => {
  fatalError.value = error instanceof Error ? error : new Error(String(error))
  return false
})

const reloadPage = () => {
  window.location.reload()
}
</script>
