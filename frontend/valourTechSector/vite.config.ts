import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const repositoryRoot = resolve(import.meta.dirname, '../..')
  const env = loadEnv(mode, repositoryRoot, '')
  const djangoTarget = env.DJANGO_PROXY_TARGET || 'http://127.0.0.1:8000'
  const proxy = Object.fromEntries(
    ['/api', '/admin', '/static', '/media'].map((path) => [path, { target: djangoTarget, changeOrigin: true }]),
  )

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      allowedHosts: ['.e2b.app'],
      proxy,
    },
    preview: {
      host: '0.0.0.0',
      allowedHosts: ['.e2b.app'],
    },
  }
})
