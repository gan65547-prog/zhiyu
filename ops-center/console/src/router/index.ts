import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/login", name: "login", component: () => import("@/views/LoginView.vue") },
    {
      path: "/",
      component: () => import("@/views/LayoutView.vue"),
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "dashboard", component: () => import("@/views/DashboardView.vue") },
        { path: "tenants", name: "tenants", component: () => import("@/views/TenantsView.vue") },
        {
          path: "writes",
          name: "writes",
          component: () => import("@/views/WritesView.vue"),
        },
        {
          path: "users",
          name: "users",
          component: () => import("@/views/UsersView.vue"),
          meta: { superAdmin: true },
        },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isAuthed) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.superAdmin && !auth.isSuperAdmin) {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
