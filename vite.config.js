import { defineConfig } from 'vite';
import viteCompression from 'vite-plugin-compression';
import vue from '@vitejs/plugin-vue2';

// https://vitejs.dev/config/
export default defineConfig({
  
  plugins: [
    vue(),
    viteCompression()
  ],

  base: './',

  server: {
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:5000/'
      }
    }
  },

  build: {
    chunkSizeWarningLimit: 600
  },

  css: { // https://github.com/vitejs/vite/issues/6333#issuecomment-1003318603
    postcss: {
      plugins: [
        {
          postcssPlugin: 'internal:charset-removal',
          AtRule: {
            charset: (atRule) => {
              if (atRule.name === 'charset') {
                atRule.remove();
              }
            }
          }
        }
      ]
    },
  }
})
