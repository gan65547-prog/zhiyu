<template>
  <h2>运维用户</h2>
  <p class="muted">仅 super_admin 可访问列表与变更接口。</p>
  <button type="button" @click="load">刷新</button>
  <table v-if="rows.length">
    <thead>
      <tr>
        <th>用户名</th>
        <th>角色</th>
        <th>启用</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="u in rows" :key="u.username">
        <td>{{ u.username }}</td>
        <td>{{ (u.roles || []).join(",") }}</td>
        <td>{{ u.is_active }}</td>
      </tr>
    </tbody>
  </table>
  <pre class="pre">{{ err }}</pre>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { http } from "@/api/http";

interface U {
  username: string;
  roles?: string[];
  is_active?: boolean;
}

const rows = ref<U[]>([]);
const err = ref("");

async function load() {
  err.value = "";
  try {
    const { data } = await http.get<{ data?: U[] }>("/api/v1/users");
    rows.value = data?.data || [];
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : String(e);
  }
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}
table {
  width: 100%;
  margin-top: 12px;
  font-size: 0.85rem;
  border-collapse: collapse;
}
th,
td {
  padding: 8px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}
.pre {
  margin-top: 12px;
  color: #fecaca;
  font-size: 0.8rem;
}
</style>
