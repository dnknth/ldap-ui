<template>
  <nav
    class="px-4 flex flex-col md:flex-row flex-wrap justify-between mt-0 py-1 bg-primary/40"
  >
    <div class="flex items-center">
      <i
        class="cursor-pointer glyph fa-bars fa-lg pt-1 mr-4 md:hidden"
        @click="collapsed = !collapsed"
      ></i>

      <i
        class="cursor-pointer fa fa-lg mr-2"
        :class="treeOpen ? 'fa-list-alt' : 'fa-list-ul'"
        @click="emit('update:treeOpen', !treeOpen)"
      ></i>
      <node-label
        oc="person"
        v-if="userDn"
        :dn="userDn"
        @select-dn="emit('update:activeDn', $event)"
        class="text-lg"
      />
    </div>

    <div class="flex items-center space-x-4 text-lg" v-show="!collapsed">
      <!-- Right aligned nav items -->
      <span class="cursor-pointer" @click="emit('update:modal', 'ldif-import')"
        >Import…</span
      >

      <dropdown-menu title="Schema">
        <li
          role="menuitem"
          v-for="key in state.schema?.objectClasses.keys() ?? []"
          :key="key"
          @click="emit('update:oc', key)"
        >
          {{ key }}
        </li>
      </dropdown-menu>

      <form @submit.prevent="search">
        <input
          class="glyph px-2 py-1 rounded focus:border focus:border-front/80 outline-none text-front dark:bg-gray-800/80"
          autofocus
          placeholder=" &#xf002;"
          name="q"
          @focusin="input?.select()"
          accesskey="k"
          @keyup.esc="query = ''"
          id="nav-search"
          ref="input"
        />
        <search-results
          for="nav-search"
          @select-dn="
            query = '';
            emit('update:activeDn', $event);
          "
          :shorten="state.baseDn"
          :query="query"
        />
      </form>

      <i
        v-if="!externalAuth"
        class="fa fa-sign-out cursor-pointer pl-2"
        title="Log out"
        @click="emit('logout')"
      ></i>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, useTemplateRef } from "vue";
import DropdownMenu from "./ui/DropdownMenu.vue";
import NodeLabel from "./NodeLabel.vue";
import SearchResults from "./SearchResults.vue";
import { state } from "@/state";
import { isExternalAuthenticated } from "@/auth";

const input = useTemplateRef("input"),
  query = ref(""),
  collapsed = ref(false),
  externalAuth = isExternalAuthenticated(),
  emit = defineEmits<{
    "update:activeDn": [dn?: string];
    "update:modal": [name: string];
    "update:oc": [name: string];
    "update:treeOpen": [open: boolean];
    logout: [];
  }>();

defineProps<{
  activeDn?: string;
  modal?: string;
  oc?: string;
  treeOpen: boolean;
  userDn?: string;
}>();

function search() {
  query.value = "";
  nextTick(() => {
    query.value = input?.value?.value || "";
  });
}

// The navbar is mounted fresh after login (v-else-if="ready" in App.vue);
// autofocus is not reliably honored for dynamically inserted elements, so
// focus the search box explicitly.
onMounted(() => {
  nextTick(() => input?.value?.focus());
});
</script>
