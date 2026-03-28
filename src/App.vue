<template>
  <div id="app">
    <nav-bar v-model:treeOpen="treeOpen" v-model:modal="modal" v-model:oc="oc" v-model:activeDn="activeDn" />
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
        <notification v-model:alert="state.alert" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import AttributeCard from "./components/schema/AttributeCard.vue";
import EntryEditor from "./components/editor/EntryEditor.vue";
import LdifImportDialog from "./components/LdifImportDialog.vue";
import NavBar from "./components/NavBar.vue";
import Notification from "./components/Notification.vue";
import ObjectClassCard from "./components/schema/ObjectClassCard.vue";
import TreeView from "./components/TreeView.vue";
import { state } from "./state";

const
  treeOpen = ref(true), // Is the tree visible?
  activeDn = ref<string>(), // currently active DN in the editor
  oc = ref<string>(), // objectClass info in side panel
  attr = ref<string>(), // attribute info in side panel
  modal = ref<string>(); // modal popup ID

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
