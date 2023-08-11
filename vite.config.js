import { defineConfig } from 'vite';
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
    manifest: true,
    chunkSizeWarningLimit: 600
  },

  server: {
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:5000/'
      }
    }
  }
})
