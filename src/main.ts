"use strict";

import { createApp } from "vue";
import App from "./App.vue";
import { initState } from "./state"
import { client } from "./generated/client.gen";
import "./app.css";
import "font-awesome/css/font-awesome.min.css";

// Adjust the base URL of the API client for relative mounts like /ldap
client.setConfig({ baseUrl: window.location.href });

initState().then(() => createApp(App).mount("#app"));
