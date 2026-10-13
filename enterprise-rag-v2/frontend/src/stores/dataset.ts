import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getDatasets as getDatasetsApi,
  getDataset as getDatasetApi,
  createDataset as createDatasetApi,
  updateDataset as updateDatasetApi,
  deleteDataset as deleteDatasetApi
} from '@/api/dataset'
import type { Dataset, CreateDatasetForm, UpdateDatasetForm } from '@/types'
import { useAuthStore } from './auth'

export const useDatasetStore = defineStore('dataset', () => {
  const datasets = ref<Dataset[]>([])
  const currentDataset = ref<Dataset | null>(null)
  const loading = ref(false)
  /** 非 silent 的列表拉取并发计数，避免多路请求互相把 loading 提前关掉 */
  let listLoadingDepth = 0
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)

  // 检查用户是否已登录
  const isLoggedIn = computed(() => {
    const authStore = useAuthStore()
    return authStore.isLoggedIn
  })

  // 检查用户是否是超级管理员
  const isSuperuser = computed(() => {
    const authStore = useAuthStore()
    return authStore.isSuperuser
  })

  async function fetchDatasets(params?: { page?: number; page_size?: number; silent?: boolean }) {
    console.log('DatasetStore fetchDatasets called with params:', params)
    console.log('DatasetStore isSuperuser:', isSuperuser.value)
    const paramsIn = params || {}
    const silent = paramsIn.silent === true
    const restParams: Record<string, unknown> = { ...paramsIn }
    delete restParams.silent
    // 超级管理员不获取数据集
    if (isSuperuser.value) {
      console.log('DatasetStore: superuser, returning empty datasets')
      datasets.value = []
      total.value = 0
      return
    }
    
    // 如果用户未登录，直接返回空数组
    if (!isLoggedIn.value) {
      console.log('DatasetStore: user not logged in, returning empty datasets')
      datasets.value = []
      total.value = 0
      return
    }
    
    if (!silent) {
      listLoadingDepth++
      loading.value = true
    }
    try {
      // 从localStorage获取当前工作空间ID
      const currentWorkspaceId = localStorage.getItem('currentWorkspaceId')
      console.log('DatasetStore currentWorkspaceId:', currentWorkspaceId)
      const queryParams: any = { ...restParams }
      if (currentWorkspaceId) {
        queryParams.workspace_id = currentWorkspaceId
        console.log('DatasetStore adding workspace_id to params:', queryParams)
      }
      console.log('DatasetStore calling getDatasetsApi with params:', queryParams)
      const res = await getDatasetsApi(queryParams)
      console.log('DatasetStore getDatasetsApi raw response:', res)
      console.log('DatasetStore res structure:', Object.keys(res))
      if (res.data) {
        console.log('DatasetStore res.data structure:', Object.keys(res.data))
      }
      datasets.value = res.items || res.data?.items || []
      total.value = res.total || res.data?.total || 0
      page.value = res.page || res.data?.page || 1
      pageSize.value = res.page_size || res.data?.page_size || 20
      console.log('DatasetStore processed datasets:', datasets.value)
      console.log('DatasetStore processed total:', total.value)
      if (datasets.value.length > 0) {
        console.log('First dataset structure:', Object.keys(datasets.value[0]))
        console.log('First dataset document_count:', datasets.value[0].document_count)
      }
      return res
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status !== 429) console.error('DatasetStore fetchDatasets error:', e)
      // 静默失败
      datasets.value = []
      total.value = 0
    } finally {
      if (!silent) {
        listLoadingDepth = Math.max(0, listLoadingDepth - 1)
        loading.value = listLoadingDepth > 0
      }
      console.log('DatasetStore fetchDatasets completed')
    }
  }

  async function fetchDataset(id: string) {
    console.log('DatasetStore fetchDataset called with id:', id)
    
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      console.log('DatasetStore: user not logged in, returning null')
      currentDataset.value = null
      return null
    }
    
    loading.value = true
    try {
      const res = await getDatasetApi(id)
      console.log('DatasetStore fetchDataset response:', res)
      currentDataset.value = res.data || res
      return res
    } catch (e: any) {
      console.error('DatasetStore fetchDataset error:', e)
      const statusCode = Number(e?.response?.status || 0)
      // 仅在明确不存在时清空；网络抖动/临时错误保留上一份数据，避免页面闪空。
      if (statusCode === 404) {
        currentDataset.value = null
      }
      return null
    } finally {
      loading.value = false
      console.log('DatasetStore fetchDataset completed')
    }
  }

  async function createDatasetApi2(data: CreateDatasetForm) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      console.error('DatasetStore: user not logged in, cannot create dataset')
      return null
    }
    
    loading.value = true
    try {
      // 从localStorage获取当前工作空间ID
      const currentWorkspaceId = localStorage.getItem('currentWorkspaceId')
      const backendData: any = {
        name: data.name,
        description: data.description,
        embedding_model: data.config?.embedding_model || 'bge-small-zh-v1.5',
        chunk_size: data.config?.chunk_size || 500,
        chunk_overlap: data.config?.chunk_overlap || 50
      }
      if (currentWorkspaceId) {
        backendData.workspace_id = currentWorkspaceId
        console.log('Adding workspace_id to dataset creation:', backendData.workspace_id)
      } else {
        console.error('No current workspace ID found!')
      }
      const res = await createDatasetApi(backendData)
      const newDataset = res.data || res
      datasets.value.push(newDataset)
      console.log('Created dataset with workspace_id:', newDataset.workspace_id)
      return newDataset
    } finally {
      loading.value = false
    }
  }

  async function updateDatasetApi2(id: string, data: UpdateDatasetForm) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      console.error('DatasetStore: user not logged in, cannot update dataset')
      return null
    }
    
    loading.value = true
    try {
      const res = await updateDatasetApi(id, data)
      const updated = res.data || res
      const index = datasets.value.findIndex(d => d.id === id)
      if (index !== -1) {
        datasets.value[index] = updated
      }
      if (currentDataset.value?.id === id) {
        currentDataset.value = updated
      }
      return updated
    } finally {
      loading.value = false
    }
  }

  async function deleteDatasetApi2(id: string) {
    // 如果用户未登录，直接返回
    if (!isLoggedIn.value) {
      console.error('DatasetStore: user not logged in, cannot delete dataset')
      return
    }
    
    loading.value = true
    try {
      await deleteDatasetApi(id)
      datasets.value = datasets.value.filter(d => d.id !== id)
      if (currentDataset.value?.id === id) {
        currentDataset.value = null
      }
    } finally {
      loading.value = false
    }
  }

  function setCurrentDataset(dataset: Dataset | null) {
    currentDataset.value = dataset
  }

  function clearError() {
    // error handling if needed
  }

  return {
    datasets,
    currentDataset,
    loading,
    total,
    page,
    pageSize,
    fetchDatasets,
    fetchDataset,
    createDataset: createDatasetApi2,
    updateDataset: updateDatasetApi2,
    deleteDataset: deleteDatasetApi2,
    setCurrentDataset,
    clearError
  }
})
