<template>
  <div id="app">
    <notification v-model:alert="state.alert" />
    <login-dialog v-if="!checking && !authenticated && loginDialog" @ok="init" />

    <template v-else-if="ready">
      <nav-bar v-model:treeOpen="treeOpen" v-model:modal="modal" v-model:oc="oc" v-model:activeDn="activeDn" :user-dn="userDn" @logout="logout" />
      <ldif-import-dialog v-model:modal="modal" @ok="activeDn = '-'" />

      <div class="flex container">
        <!-- left column -->
        <div class="space-y-4">
          <tree-view v-model:activeDn="activeDn" v-show="treeOpen" />
          <object-class-card v-model="oc" @show-attr="attr = $event" />
          <attribute-card v-model="attr" />
        </div>

        <!-- main editor -->
        <div class="flex-auto mt-4">
          <entry-editor v-model:activeDn="activeDn" @show-attr="attr = $event" @show-oc="oc = $event" />
        </div>
      </div>

      <div v-if="false"><!-- Not rendered, prevents color pruning -->
        <span class="text-primary bg-primary"></span>
        <span class="text-back bg-back"></span>
        <span class="text-danger bg-danger"></span>
        <span class="text-front bg-front"></span>
        <span class="text-secondary bg-secondary"></span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import AttributeCard from "./components/schema/AttributeCard.vue";
import EntryEditor from "./components/editor/EntryEditor.vue";
import LdifImportDialog from "./components/LdifImportDialog.vue";
import LoginDialog from "./components/LoginDialog.vue";
import NavBar from "./components/NavBar.vue";
import Notification from "./components/Notification.vue";
import ObjectClassCard from "./components/schema/ObjectClassCard.vue";
import TreeView from "./components/TreeView.vue";
import { initState, state } from "./state";
import { getWhoAmI } from "@/generated";
import { setCredentials, clearCredentials, isAuthenticated, setExternalAuthenticated, clearExternalAuthenticated } from "./auth";

const
  treeOpen = ref(true), // Is the tree visible?
  activeDn = ref<string>(), // currently active DN in the editor
  oc = ref<string>(), // objectClass info in side panel
  attr = ref<string>(), // attribute info in side panel
  modal = ref<string>(), // modal popup ID
  loginDialog = ref(true), // show the login dialog (only relevant when !authenticated)
  checking = ref(true), // true while the startup auth check runs (nothing rendered, avoids dialog flash)
  authenticated = computed(isAuthenticated),
  userDn = ref<string>(), // DN of the current user (already probed once)
  ready = ref(false); // initState() has completed

onMounted(async () => {
  if (authenticated.value) {
    await initState();
    ready.value = true;
  } else {
    await probeExternalAuth();
  }
  checking.value = false;
});

// An upstream HTTP server (or a native browser Basic challenge) may already
// have authenticated the session by supplying the Authorization header. Probe
// /api/whoami: if it succeeds, skip the login dialog.
async function probeExternalAuth() {
  const response = await getWhoAmI();
  // No external auth: either the upstream rejected/omitted the Authorization
  // header (401), or no credentials reached the directory (200 + empty DN).
  // Either way, fall back to the login dialog.
  if (response.response?.status === 401 || response.data === "") return;
  // A genuine server/network error cannot confirm external auth either, but it
  // is not an authentication failure, so don't prompt for a login — surface
  // the error instead.
  if (response.error || !response.data) {
    loginDialog.value = false;
    state.showException("Unable to determine authentication status");
    return;
  }
  userDn.value = response.data;
  setExternalAuthenticated();
  await initState();
  ready.value = true;
}

async function init(username: string, password: string) {
  setCredentials(username, password);
  const response = await getWhoAmI();
  if (response.data) userDn.value = response.data;
  await initState();
  ready.value = true;
}

function logout() {
  clearCredentials();
  clearExternalAuthenticated();
  userDn.value = undefined;
  loginDialog.value = true;
  state.reset();
  ready.value = false;
}

watch(attr, (a) => {
  if (a) oc.value = undefined;
});
watch(oc, (o) => {
  if (o) attr.value = undefined;
});
</script>

<style>
.control {
  @apply opacity-70 hover:opacity-90 cursor-pointer select-none leading-none pt-1 pr-1;
}

button,
.btn,
[type="button"] {
  @apply px-3 py-2 rounded text-back dark:text-front font-medium outline-none;
}

button.btn {
  @apply border-solid border-back border-2 focus:border-primary dark:focus:border-front;
}

select {
  background: url(data:image/svg+xml;base64,PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2IDEwIj4KICA8cG9seWdvbiBmaWxsPSJncmF5IiBwb2ludHM9IjEuNDEgNC42NyAyLjQ4IDMuMTggMy41NCA0LjY3IDEuNDEgNC42NyIgLz4KICA8cG9seWdvbiBmaWxsPSJncmF5IiBwb2ludHM9IjMuNTQgNS4zMyAyLjQ4IDYuODIgMS40MSA1LjMzIDMuNTQgNS4zMyIgLz4KPC9zdmc+) no-repeat right;
  appearance: none;
}

.glyph {
  font-family: sans-serif, FontAwesome;
  font-style: normal;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
