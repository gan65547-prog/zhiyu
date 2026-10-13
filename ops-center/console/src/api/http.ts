import axios, { type AxiosInstance } from "axios";
import { useAuthStore } from "@/stores/auth";

const base = import.meta.env.BASE_URL.replace(/\/$/, "");

export const http: AxiosInstance = axios.create({
  baseURL: base || "/",
  timeout: 30000,
});

http.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore();
      auth.clear();
      if (!window.location.pathname.endsWith("/login")) {
        window.location.href = `${import.meta.env.BASE_URL}login`;
      }
    }
    return Promise.reject(err);
  },
);
