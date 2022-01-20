import 'core-js/stable'
import 'regenerator-runtime/runtime'
import 'intersection-observer' // Optional
import './assets/theme.css'
import 'font-awesome/css/font-awesome.min.css'
import Vue from 'vue'
import './plugins/bootstrap-vue'
import App from './App.vue'

Vue.config.productionTip = false

new Vue({
  render: h => h(App),
}).$mount('#app')
