<template>
  <div class="wrap">
    <div class="card">
      <h1>ops-center 控制台</h1>
      <p class="muted">独立 Vue 前端 · 登录后按 RBAC 显示写操作入口</p>
      <label>用户名</label>
      <input v-model="username" autocomplete="username" />
      <label style="margin-top: 10px">密码</label>
      <input v-model="password" type="password" autocomplete="current-password" />
      <div class="row">
        <button type="button" @click="submit">登录</button>
        <button type="button" class="secondary" @click="fillDefault">默认 admin</button>
      </div>
      <div v-if="err" class="err">{{ err }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import axios from "axios";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const username = ref("admin");
const password = ref("");
const err = ref("");

function fillDefault() {
  username.value = "admin";
  password.value = "";
}

async function submit() {
  err.value = "";
  try {
    const base = import.meta.env.BASE_URL.replace(/\/$/, "") || "";
    const { data } = await axios.post(`${base}/api/v1/auth/login`, {
      username: username.value.trim(),
      password: password.value,
    });
    const t = data?.data?.access_token;
    if (!t) throw new Error("无 access_token");
    auth.applyToken(t);
    const red = (route.query.redirect as string) || `${import.meta.env.BASE_URL}`;
    await router.replace(red || "/");
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : String(e);
  }
}
</script>

<style scoped>
.wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.card {
  width: 100%;
  max-width: 400px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px;
}
h1 {
  margin: 0 0 8px;
  font-size: 1.15rem;
}
.muted {
  color: var(--muted);
  font-size: 0.82rem;
  margin: 0 0 16px;
}
.row {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
label {
  display: block;
  font-size: 0.75rem;
  color: var(--muted);
  margin-bottom: 4px;
}
</style>
