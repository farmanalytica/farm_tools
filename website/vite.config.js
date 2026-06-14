import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Served at the custom domain root (farmtools.com.br) via GitHub Pages, so the
// base is '/'. Uses history mode with 404.html redirect for clean URLs.
export default defineConfig({
  base: '/',
  plugins: [vue()],
})
