import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端 FastAPI 默认运行在 8000 端口，通过代理避免跨域
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/answer': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/revoke': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  }
})