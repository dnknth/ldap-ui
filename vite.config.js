import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue2';

// https://vitejs.dev/config/
export default defineConfig({
  
  plugins: [vue()],

  base: './',

  server: {
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:5000/'
      }
    }
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
