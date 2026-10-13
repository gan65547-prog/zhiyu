<template>
  <div class="loading-spinner">
    <div class="spinner" />
    <p v-if="text">
      {{ text }}
    </p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  text?: string
}>()
</script>

<style scoped lang="scss">
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #e4e7ed;
    border-top-color: #704ac6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  p {
    margin: 0;
    font-size: 14px;
    color: #827a90;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
