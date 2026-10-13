<template>
  <h2>租户</h2>
  <div class="row">
    <input v-model="keyword" placeholder="关键词" style="max-width: 200px" />
    <button type="button" @click="load">查询</button>
  </div>
  <table v-if="rows.length">
    <thead>
      <tr>
        <th>ID</th>
        <th>名称</th>
        <th>计划（历史字段）</th>
        <th>状态</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="r in rows" :key="r.id">
        <td class="mono">{{ r.id }}</td>
        <td>{{ r.name }}</td>
        <td>{{ r.plan || "—" }}</td>
        <td>{{ r.status }}</td>
      </tr>
    </tbody>
  </table>
  <p v-else class="muted">暂无数据或未加载</p>
  <pre class="pre">{{ detail }}</pre>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { http } from "@/api/http";

interface TenantRow {
  id: string;
  name?: string;
  plan?: string;
  status?: string;
}

const keyword = ref("");
const rows = ref<TenantRow[]>([]);
const detail = ref("");

async function load() {
  const q = new URLSearchParams({ page: "1", page_size: "50" });
  if (keyword.value.trim()) q.set("keyword", keyword.value.trim());
  const { data } = await http.get<{ data?: TenantRow[]; meta?: unknown }>(`/api/v1/operations/tenants?${q}`);
  rows.value = data?.data || [];
  detail.value = JSON.stringify(data?.meta || {}, null, 2);
}
</script>

<style scoped>
.row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
th,
td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--border);
}
.muted {
  color: var(--muted);
}
.pre {
  margin-top: 12px;
  font-size: 0.72rem;
  background: #0e1728;
  padding: 10px;
  border-radius: 8px;
  max-height: 200px;
  overflow: auto;
}
</style>
