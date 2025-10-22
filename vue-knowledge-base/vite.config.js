import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  
  // (新增) 添加这个 server 配置
  server: {
    proxy: {
      // 字符串简写
      // '/api': 'http://localhost:8000'
      
      // (推荐) 选项配置
      '/api/v1': {
        target: 'http://localhost:8000', // 您的 FastAPI 后端地址
        changeOrigin: true, // 必须设置为 true，用于支持跨域
        // (可选) 如果您的 API 路径中没有 /api/v1，可以用这个重写
        // rewrite: (path) => path.replace(/^\/api\/v1/, '') 
      }
    }
  }
})