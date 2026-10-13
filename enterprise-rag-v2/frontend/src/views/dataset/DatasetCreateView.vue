<template>
  <div class="dataset-create-view">
    <div class="header">
      <h1>新建知识库</h1>
      <div>
        <p class="eyebrow">KNOWLEDGE BASE / SETUP</p>
        <p class="subtitle">创建一个可检索、可引用、可继续沉淀的资料空间。</p>
      </div>
    </div>

    <el-card class="form-card">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item
          label="名称"
          prop="name"
        >
          <el-input
            v-model="form.name"
            placeholder="请输入知识库名称"
          />
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入知识库描述（可选）"
          />
        </el-form-item>

        <el-divider content-position="left">
          高级配置
        </el-divider>

        <el-form-item label="Embedding模型">
          <el-select
            v-model="form.config.embedding_model"
            placeholder="请选择"
          >
            <el-option
              label="bge-small-zh-v1.5（本地默认）"
              value="bge-small-zh-v1.5"
            />
            <el-option
              label="bge-large-zh-v1.5（需部署模型）"
              value="bge-large-zh-v1.5"
            />
            <el-option
              label="bge-base-zh-v1.5"
              value="bge-base-zh-v1.5"
            />
            <el-option
              label="text2vec-base"
              value="text2vec-base"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="检索模型">
          <el-select
            v-model="form.config.retrieval_model"
            placeholder="请选择"
          >
            <el-option
              label="语义检索"
              value="semantic"
            />
            <el-option
              label="全文检索"
              value="full_text"
            />
            <el-option
              label="混合检索"
              value="hybrid"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="块大小">
          <el-input-number
            v-model="form.config.chunk_size"
            :min="100"
            :max="2000"
            :step="100"
          />
        </el-form-item>

        <el-form-item label="块重叠">
          <el-input-number
            v-model="form.config.chunk_overlap"
            :min="0"
            :max="500"
            :step="10"
          />
        </el-form-item>

        <el-form-item>
          <el-button @click="router.push('/datasets')">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="loading"
            @click="handleSubmit"
          >
            创建
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'

const router = useRouter()
const datasetStore = useDatasetStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  name: '',
  description: '',
  config: {
    embedding_model: 'bge-small-zh-v1.5',
    retrieval_model: 'semantic',
    chunk_size: 500,
    chunk_overlap: 50
  }
})

const rules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }]
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await datasetStore.createDataset(form)
        ElMessage.success('创建成功')
        router.push('/datasets')
      } catch (e) {
        // error handled by interceptor
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped lang="scss">
.dataset-create-view {
  max-width: 900px;
  padding-bottom: 32px;

  .header {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 24px;

    h1 {
      margin: 0;
      font-size: 32px;
      font-weight: 760;
      letter-spacing: -0.04em;
      color: #241d2e;
    }

    .eyebrow { margin: 0; color: #704ac6; font-size: 11px; font-weight: 800; letter-spacing: .18em; }
    .subtitle { margin: 0; color: #827a90; font-size: 14px; }
  }

  .form-card {
    border: 1px solid rgba(124, 77, 200, 0.14);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.86);
    box-shadow: 0 18px 40px rgba(62, 42, 108, 0.08);
    backdrop-filter: blur(10px);

    :deep(.el-divider__text) { color: #704ac6; font-weight: 700; background: transparent; }
    :deep(.el-form-item__label) { color: #514a5d; font-weight: 600; }
  }
}
</style>
