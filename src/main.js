"use strict";

import Vue from 'vue';
import App from './App.vue';

import './tailwind.css';
import 'font-awesome/css/font-awesome.min.css';

Vue.config.productionTip = false;

new Vue({
  render: h => h(App),
}).$mount('#app');
