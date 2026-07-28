import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En dev, /api se proxea al backend FastAPI (uvicorn en 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
