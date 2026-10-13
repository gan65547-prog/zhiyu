import { defineStore } from "pinia";
import { ref, computed } from "vue";

const TOKEN_KEY = "ops_console_token";

function parseJwt(token: string): Record<string, unknown> {
  try {
    const p = token.split(".")[1];
    const json = atob(p.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return {};
  }
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(null);
  const username = ref("");
  const roles = ref<string[]>([]);

  const isAuthed = computed(() => Boolean(token.value));

  const canTenantWrite = computed(() => {
    const s = new Set(roles.value);
    return s.has("super_admin") || s.has("tenant_ops");
  });
  const isSuperAdmin = computed(() => roles.value.includes("super_admin"));

  function applyToken(t: string | null) {
    token.value = t;
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
      const pl = parseJwt(t);
      username.value = String(pl.sub || "");
      roles.value = Array.isArray(pl.roles) ? (pl.roles as string[]) : [];
    } else {
      localStorage.removeItem(TOKEN_KEY);
      username.value = "";
      roles.value = [];
    }
  }

  function clear() {
    applyToken(null);
  }

  if (typeof localStorage !== "undefined") {
    const existing = localStorage.getItem(TOKEN_KEY);
    if (existing) {
      applyToken(existing);
    }
  }

  return { token, username, roles, isAuthed, canTenantWrite, isSuperAdmin, applyToken, clear };
});
