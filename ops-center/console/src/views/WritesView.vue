<template>
  <h2>写操作</h2>
  <p class="muted">按 RBAC 管理自托管资源配额与索引；无权限时仅提示。</p>

  <div class="ctx card">
    <label>tenant_id</label>
    <input v-model="tenantId" class="mono" />
    <div class="row2">
      <div>
        <label>X-Op-Id</label>
        <input v-model="opId" class="mono" />
      </div>
      <div>
        <label>X-Operator</label>
        <input v-model="operator" />
      </div>
    </div>
    <button type="button" class="secondary" @click="genOp">生成 Op-Id</button>
  </div>

  <div v-if="auth.canTenantWrite" class="card">
    <h3>租户域 · 配额</h3>
    <textarea v-model="quotaBody" rows="3" class="mono" />
    <button type="button" @click="doQuota">执行配额</button>
  </div>
  <p v-else class="muted">当前角色无租户写权限（需 tenant_ops 或 super_admin）</p>

  <pre class="pre">{{ out }}</pre>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { http } from "@/api/http";

const auth = useAuthStore();
const tenantId = ref("");
const opId = ref(`ops-vue-${Date.now()}`);
const operator = ref("vue_console");
const quotaBody = ref(
  JSON.stringify({ quota_type: "documents", value: 100, reason: "vue-console" }, null, 2),
);
const out = ref("");

function genOp() {
  opId.value = `ops-vue-${Date.now()}`;
}

async function doQuota() {
  out.value = "";
  if (!tenantId.value.trim()) {
    out.value = "请填写 tenant_id";
    return;
  }
  try {
    const body = JSON.parse(quotaBody.value);
    const { data } = await http.post(
      `/api/v1/operations/tenants/${encodeURIComponent(tenantId.value.trim())}/quota`,
      body,
      { headers: { "X-Op-Id": opId.value, "X-Operator": operator.value } },
    );
    out.value = JSON.stringify(data, null, 2);
  } catch (e: unknown) {
    out.value = e instanceof Error ? e.message : JSON.stringify(e);
  }
}
</script>

<style scoped>
.muted {
  color: var(--muted);
  font-size: 0.82rem;
}
.ctx {
  margin-bottom: 16px;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 10px 0;
}
h3 {
  margin: 0 0 8px;
  font-size: 0.95rem;
}
label {
  font-size: 0.72rem;
  color: var(--muted);
}
.pre {
  margin-top: 14px;
  font-size: 0.75rem;
  background: #0e1728;
  padding: 12px;
  border-radius: 8px;
  max-height: 360px;
  overflow: auto;
}
button {
  margin-top: 8px;
}
</style>
