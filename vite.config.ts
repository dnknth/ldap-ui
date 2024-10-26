import { defineConfig } from 'vite';
import { fileURLToPath, URL } from 'node:url';
import viteCompression from 'vite-plugin-compression';
import vue from '@vitejs/plugin-vue';

// https://vitejs.dev/config/
export default defineConfig({
  
  plugins: [
    vue(),
    viteCompression()
  ],

  base: './',

  build: {
    chunkSizeWarningLimit: 600,
    outDir: 'backend/ldap_ui/statics'
  },

  

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  
  server: {
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:5000/'
      }
    }
  }
})
