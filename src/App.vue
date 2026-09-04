<template>
  <div id="app">
    <notification v-model:alert="state.alert" />
    <div
      v-if="authTrap"
      class="rounded mx-4 mt-2 p-3 border border-danger bg-danger/80 text-front dark:text-front"
      role="alert"
    >
      <b>Authentication configuration problem.</b> The login credentials
      work at the browser level but are rejected by the LDAP directory, so
      the application cannot be used. Fix the credentials on the upstream
      server or in the directory.
    </div>
    <div
      v-if="probeErrors.length"
      class="rounded mx-4 mt-2 p-3 border border-danger bg-danger/80 text-front dark:text-front"
      role="alert"
    >
      <p v-for="(d, i) in probeErrors" :key="i" class="m-0">{{ d.message }}</p>
    </div>
    <div
      v-if="probeWarnings.length"
      class="rounded mx-4 mt-2 p-3 border border-amber-400 bg-amber-200/80 text-front dark:text-front"
      role="alert"
    >
      <b>Configuration warnings:</b>
      <ul class="list-disc pl-5">
        <li v-for="(d, i) in probeWarnings" :key="i">{{ d.message }}</li>
      </ul>
    </div>
    <login-dialog v-if="!checking && !probeErrors.length && !authTrap && !authenticated && loginDialog" @ok="init" />

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
import { getWhoAmI, probe } from "@/generated";
import type { Diagnostic } from "@/generated";
import { setCredentials, clearCredentials, isAuthenticated, isExternalAuthBroken, setExternalAuthenticated, clearExternalAuthenticated } from "./auth";

const
  treeOpen = ref(true), // Is the tree visible?
  activeDn = ref<string>(), // currently active DN in the editor
  oc = ref<string>(), // objectClass info in side panel
  attr = ref<string>(), // attribute info in side panel
  modal = ref<string>(), // modal popup ID
  loginDialog = ref(true), // show the login dialog (only relevant when !authenticated)
  checking = ref(true), // true while the startup auth check runs (nothing rendered, avoids dialog flash)
  authenticated = computed(isAuthenticated),
  authTrap = computed(() => isExternalAuthBroken()),
  probeErrors = ref<Diagnostic[]>([]), // error diagnostics from the /probe endpoint
  probeWarnings = ref<Diagnostic[]>([]), // warning diagnostics from the /probe endpoint
  userDn = ref<string>(), // DN of the current user (already probed once)
  ready = ref(false); // initState() has completed

onMounted(async () => {
  checking.value = true;
  await probeLdap();
  if (probeErrors.value.length) {
    // Directory not usable (unreachable or misconfigured): show only the
    // banner, no login dialog.
    checking.value = false;
    return;
  }
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

async function probeLdap() {
  // Check that the LDAP directory is reachable and usable. This is distinct
  // from authentication: a failed probe means the deployment itself is broken
  // (bad LDAP_URL, directory down, or anonymous reads denied where required).
  const response = await probe();
  probeErrors.value = [];
  probeWarnings.value = [];
  // Surface every diagnostic from the probe directly: errors in the red
  // banner (unreachable directory, missing/unreadable base or schema),
  // warnings in the amber one (insecure TLS, denied anonymous reads).
  const result = response.data;
  if (!result) {
    // The probe itself failed (no /api/probe response): fall back to a
    // synthetic unreachable diagnostic.
    probeErrors.value = [
      {
        severity: "error",
        message:
          "Cannot connect to the LDAP directory. Check LDAP_URL.",
      },
    ];
    return;
  }
  probeErrors.value = (result.diagnostics ?? []).filter(
    (d) => d.severity === "error",
  );
  probeWarnings.value = (result.diagnostics ?? []).filter(
    (d) => d.severity === "warning",
  );
}

async function init(username: string, password: string) {
  setCredentials(username, password);
  clearExternalAuthenticated(); // fresh start: flush any external-auth trap flag
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
