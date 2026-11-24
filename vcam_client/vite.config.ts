import fs from 'node:fs'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// branding.json: product name, logo and default theme in one place (see src/theme.css for colors)
const brandingPath = path.resolve(import.meta.dirname, './branding.json')
const branding = JSON.parse(fs.readFileSync(brandingPath, 'utf8')) as { productName?: unknown; logo?: unknown; defaultTheme?: unknown }
for (const key of ['productName', 'logo'] as const) {
  if (typeof branding[key] !== 'string' || !(branding[key] as string).trim()) throw new Error(`${brandingPath}: ${key} must be a non-empty string`)
}
const productName = (branding.productName as string).trim()
const productLogo = (branding.logo as string).trim()
const defaultTheme = typeof branding.defaultTheme === 'string' ? branding.defaultTheme : 'dusk'

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, 'VITE_')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:9000'
  const cameraTarget = env.VITE_CAMERA_TARGET || 'http://127.0.0.1:8004'
  return {
    plugins: [
      {
        name: 'vcamx-branding',
        transformIndexHtml: (html: string) => html
          .replaceAll('__PRODUCT_NAME__', escapeHtml(productName))
          .replaceAll('__PRODUCT_LOGO__', escapeHtml(productLogo))
          .replaceAll('__DEFAULT_THEME__', escapeHtml(defaultTheme)),
      },
      react(),
      tailwindcss(),
    ],
    define: {
      __PRODUCT_NAME__: JSON.stringify(productName),
      __PRODUCT_LOGO__: JSON.stringify(productLogo),
      __DEFAULT_THEME__: JSON.stringify(defaultTheme),
    },
    resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
    // 5180 like nvr_client. Manager UI: http://localhost:5180/  Camera page: http://localhost:5180/camera.html
    server: {
      port: 3000,
      strictPort: true,
      host: true,
      proxy: {
        '/api/v1': { target: apiTarget, ws: true, changeOrigin: true },
        // Camera Web Page talks to ONE camera listener (pick it with VITE_CAMERA_TARGET)
        '/api/cam': { target: cameraTarget, changeOrigin: true },
      },
    },
    // Both apps in one build; vcam_server serves index.html on :9000 and camera.html on every camera port
    build: {
      outDir: path.resolve(import.meta.dirname, '../vcam_server/static/web'),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          manager: path.resolve(import.meta.dirname, 'index.html'),
          camera: path.resolve(import.meta.dirname, 'camera.html'),
        },
      },
    },
  }
})
