import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

const backendProxy = {
  '^/api/': {
    target: process.env.VITE_DEV_API || 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path: string) => path
  },
  '/ws': {
    target: process.env.VITE_DEV_WS || 'ws://127.0.0.1:8000',
    ws: true
  }
}

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts'
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts'
    })
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
          @use "@/styles/tokens/colors" as *;
          @use "@/styles/tokens/typography" as *;
          @use "@/styles/tokens/spacing" as *;
          @use "@/styles/tokens/radius" as *;
          @use "@/styles/tokens/shadows" as *;
          @use "@/styles/tokens/transitions" as *;
        `,
        api: 'modern-compiler'
      }
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: backendProxy
  },
  preview: {
    port: 3000,
    host: '127.0.0.1',
    proxy: backendProxy
  }
})
