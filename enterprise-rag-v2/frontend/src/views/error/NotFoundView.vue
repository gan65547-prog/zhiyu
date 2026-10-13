<template>
  <div class="not-found-view">
    <div class="content">
      <h1>404</h1>
      <p>抱歉，您访问的页面不存在</p>
      <el-button
        type="primary"
        @click="router.push('/')"
      >
        返回首页
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped lang="scss">
.not-found-view {
  height: calc(100vh - 60px - 40px);
  display: flex;
  align-items: center;
  justify-content: center;

  .content {
    text-align: center;

    h1 {
      font-size: 120px;
      font-weight: 700;
      color: #704ac6;
      margin: 0;
      line-height: 1;
    }

    p {
      font-size: 18px;
      color: #606266;
      margin: 20px 0 30px;
    }
  }
}
</style>
