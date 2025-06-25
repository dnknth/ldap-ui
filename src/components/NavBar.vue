<template>
  <nav class="px-4 flex flex-col md:flex-row flex-wrap justify-between mt-0 py-1 bg-primary/40">
    <div class="flex items-center">
      <i class="cursor-pointer glyph fa-bars fa-lg pt-1 mr-4 md:hidden" @click="collapsed = !collapsed"></i>

      <i class="cursor-pointer fa fa-lg mr-2" :class="treeOpen ? 'fa-list-alt' : 'fa-list-ul'"
        @click="emit('update:treeOpen', !treeOpen)"></i>
      <node-label oc="person" :dn="user" @select-dn="emit('select-dn', $event)" class="text-lg" />
    </div>

    <div class="flex items-center space-x-4 text-lg" v-show="!collapsed">
      <!-- Right aligned nav items -->
      <span class="cursor-pointer" @click="emit('show-modal', 'ldif-import')">Import…</span>

      <dropdown-menu title="Schema">
        <li role="menuitem" v-for="key in app?.schema.objectClasses.keys()" :key="key" @click="emit('show-oc', key)">
          {{ key }}
        </li>
      </dropdown-menu>

      <form @submit.prevent="search">
        <input
          class="glyph px-2 py-1 rounded focus:border focus:border-front/80 outline-none text-front dark:bg-gray-800/80"
          autofocus :placeholder="' \uf002'" name="q" @focusin="input?.select()" accesskey="k" @keyup.esc="query = ''"
          id="nav-search" ref="input" />
        <search-results for="nav-search" @select-dn="
          query = '';
        emit('select-dn', $event);
        " :shorten="baseDn" :query="query" />
      </form>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { inject, nextTick, ref } from "vue";
import DropdownMenu from "./ui/DropdownMenu.vue";
import type { Provided } from "./Provided";
import NodeLabel from "./NodeLabel.vue";
import SearchResults from "./SearchResults.vue";

const app = inject<Provided>("app"),
  input = ref<HTMLInputElement | null>(null),
  query = ref(""),
  collapsed = ref(false),
  emit = defineEmits<{
    "select-dn": [dn?: string];
    "show-modal": [name: string];
    "show-oc": [name: string];
    "update:treeOpen": [open: boolean];
  }>();

defineProps<{
  baseDn?: string;
  treeOpen: boolean;
  user: string;
}>();

function search() {
  query.value = "";
  nextTick(() => {
    query.value = input?.value?.value || "";
  });
}
</script>
