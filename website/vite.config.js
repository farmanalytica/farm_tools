import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Served at the custom domain root (farmtools.com.br) via GitHub Pages, so the
// base is '/'. Routing uses hash history, so no SPA 404 fallback is needed.
export default defineConfig({
  base: '/',
  plugins: [vue()],
})
