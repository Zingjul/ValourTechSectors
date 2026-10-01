import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const repositoryRoot = resolve(import.meta.dirname, '../..')
  // Server-side config only. No credentials are injected into the browser.
  const env = { ...loadEnv(mode, repositoryRoot, ''), ...process.env }
  const djangoTarget = env.DJANGO_PROXY_TARGET || 'http://127.0.0.1:8000'
  // changeOrigin stays off so Django sees the host the browser actually used,
  // exactly as it does behind Render. Absolute URLs Django builds — the
  // invitation links staff copy out of the admin — then match the origin being
  // browsed, and a hostname missing from DJANGO_ALLOWED_HOSTS shows up here
  // rather than only in production.
  const proxy = Object.fromEntries(
    ['/api', '/admin', '/static/admin', '/media'].map((path) => [path, { target: djangoTarget }]),
  )

  return {
    plugins: [react()],
    build: {
      // Django collects dist/static into /static; index.html stays at the site root.
      // Unlike changing Vite's base, this also keeps preview/deep links working.
      assetsDir: 'static/site/assets',
      sourcemap: false,
    },
    server: {
      host: '0.0.0.0',
      allowedHosts: ['.e2b.app'],
      proxy,
    },
    preview: {
      host: '0.0.0.0',
      allowedHosts: ['.e2b.app'],
      proxy,
    },
  }
})
