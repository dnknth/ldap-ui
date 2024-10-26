<template>
  <div id="app" v-if="user">
    <nav-bar v-model:treeOpen="treeOpen" :dn="activeDn" :base-dn="baseDn" :user="user" @show-modal="modal = $event;"
      @select-dn="activeDn = $event;" @show-oc="oc = $event;" />

    <ldif-import-dialog v-model:modal="modal" @ok="activeDn = '-';" />

    <div class="flex container">
      <div class="space-y-4"><!-- left column -->
        <tree-view v-model:activeDn="activeDn" v-show="treeOpen" @base-dn="baseDn = $event;" />
        <object-class-card v-model="oc" @show-attr="attr = $event;" @show-oc="oc = $event;" />
        <attribute-card v-model="attr" @show-attr="attr = $event;" />
      </div>

      <div class="flex-auto mt-4"><!-- main editing area -->
        <transition name="fade"><!-- Notifications -->
          <div v-if="error" :class="error.cssClass"
            class="rounded mx-4 mb-4 p-3 border border-front/70 text-front/70 dark:text-back/70">
            {{ error.msg }}
            <span class="float-right control" @click="error = undefined">✖</span>
          </div>
        </transition>

        <entry-editor v-model:activeDn="activeDn" :user="user" @show-attr="attr = $event;" @show-oc="oc = $event;" />
      </div>
    </div>

    <div v-if="false"><!-- Not rendered, prevents color pruning -->
      <span class="text-primary bg-primary"></span>
      <span class="text-back bg-back"></span>
      <span class="text-danger bg-danger"></span>
      <span class="text-front bg-front"></span>
      <span class="text-secondary bg-secondary"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, provide, ref, watch } from 'vue';
import AttributeCard from './components/schema/AttributeCard.vue';
import EntryEditor from './components/editor/EntryEditor.vue';
import { LdapSchema } from './components/schema/schema';
import LdifImportDialog from './components/LdifImportDialog.vue';
import NavBar from './components/NavBar.vue';
import ObjectClassCard from './components/schema/ObjectClassCard.vue';
import type { Provided } from './components/Provided';
import TreeView from './components/TreeView.vue';

interface Error {
  counter: number;
  cssClass: string;
  msg: string
}

const
  // Authentication
  user = ref<string>(),      // logged in user
  baseDn = ref<string>(),

  // Components
  treeOpen = ref(true),      // Is the tree visible?
  activeDn = ref<string>(),  // currently active DN in the editor
  modal = ref<string>(),     // modal popup

  // Alerts
  error = ref<Error>(),      // status alert

  // LDAP schema
  schema = ref<LdapSchema>(),
  oc = ref<string>(),        // objectClass info in side panel
  attr = ref<string>(),      // attribute info in side panel

  // Helpers for components
  provided: Provided = {
    get schema() { return schema.value; },
    showInfo,
    showError,
    showException,
    showWarning,
  };

provide('app', provided);

onMounted(async () => { // Runs on page load
  // Get the DN of the current user
  const whoamiResponse = await fetch('api/whoami');
  if (whoamiResponse.ok) {
    user.value = await whoamiResponse.json();
  }

  // Load the schema
  const schemaResponse = await fetch('api/schema');
  if (schemaResponse.ok) {
    schema.value = new LdapSchema(await schemaResponse.json());
  }
});

watch(attr, (a) => { if (a) oc.value = undefined; });
watch(oc, (o) => { if (o) attr.value = undefined; });

// Display an info popup
function showInfo(msg: string) {
  error.value = { counter: 5, cssClass: 'bg-emerald-300', msg: '' + msg };
  setTimeout(() => { error.value = undefined; }, 5000);
}

// Flash a warning popup
function showWarning(msg: string) {
  error.value = { counter: 10, cssClass: 'bg-amber-200', msg: '⚠️ ' + msg };
  setTimeout(() => { error.value = undefined; }, 10000);
}

// Report an error
function showError(msg: string) {
  error.value = { counter: 60, cssClass: 'bg-red-300', msg: '⛔ ' + msg };
  setTimeout(() => { error.value = undefined; }, 60000);
}

function showException(msg: string) {
  const span = document.createElement('span');
  span.innerHTML = msg.replace("\n", " ");
  const titles = span.getElementsByTagName('title');
  for (let i = 0; i < titles.length; ++i) {
    span.removeChild(titles[i]);
  }
  let text = '';
  const headlines = span.getElementsByTagName('h1');
  for (let i = 0; i < headlines.length; ++i) {
    text = text + headlines[i].textContent + ': ';
    span.removeChild(headlines[i]);
  }
  showError(text + ' ' + span.textContent);
}
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
