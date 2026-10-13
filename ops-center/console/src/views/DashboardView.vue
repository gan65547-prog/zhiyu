<template>
  <h2>概览</h2>
  <div class="grid">
    <div class="card">
      <div class="k">业务上游</div>
      <div class="v">{{ upstreamText }}</div>
    </div>
    <div class="card">
      <div class="k">租户样本数</div>
      <div class="v">{{ tenantSample }}</div>
    </div>
  </div>
  <pre class="pre">{{ raw }}</pre>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { http } from "@/api/http";

const upstreamText = ref("-");
const tenantSample = ref("-");
const raw = ref("");

onMounted(async () => {
  try {
    const [upRes, tRes] = await Promise.all([
      http.get("/api/v1/operations/health/upstream"),
      http.get("/api/v1/operations/tenants?page=1&page_size=5"),
    ]);
    const u = upRes.data as Record<string, unknown>;
    const t = tRes.data as { data?: unknown[]; meta?: unknown };
    upstreamText.value =
      u?.status === "ok" ? "可达" : u?.status === "degraded" ? "降级" : String(u?.status ?? JSON.stringify(u).slice(0, 40));
    tenantSample.value = String(t.data?.length ?? 0);
    raw.value = JSON.stringify({ upstream: u, tenants_meta: t.meta }, null, 2);
  } catch (e) {
    raw.value = String(e);
  }
});
</script>

<style scoped>
h2 {
  margin-top: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
}
.k {
  font-size: 0.72rem;
  color: var(--muted);
}
.v {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 4px;
}
.pre {
  background: #0e1728;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  font-size: 0.75rem;
  overflow: auto;
  max-height: 420px;
}
</style>
