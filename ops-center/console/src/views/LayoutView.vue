<template>
  <div class="layout">
    <aside class="side">
      <div class="brand">ops-center</div>
      <nav>
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/tenants">租户</RouterLink>
        <RouterLink to="/writes">写操作</RouterLink>
        <RouterLink v-if="auth.isSuperAdmin" to="/users">运维用户</RouterLink>
      </nav>
      <div class="foot">
        <div class="who">{{ auth.username }} · {{ auth.roles.join(",") || "-" }}</div>
        <button class="ghost" type="button" @click="logout">退出</button>
      </div>
    </aside>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

async function logout() {
  auth.clear();
  await router.replace("/login");
}
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.side {
  width: 200px;
  border-right: 1px solid var(--border);
  background: #0e1728;
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
}
.brand {
  font-weight: 700;
  margin-bottom: 16px;
  color: #93c5fd;
}
nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
nav a {
  text-decoration: none;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--text);
  font-size: 0.88rem;
}
nav a.router-link-active {
  background: #1e3a5f;
  color: #fff;
}
.foot {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.who {
  font-size: 0.72rem;
  color: var(--muted);
  margin-bottom: 8px;
  word-break: break-all;
}
.main {
  flex: 1;
  padding: 20px 24px;
  overflow: auto;
}
</style>
