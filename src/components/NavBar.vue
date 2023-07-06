<template>
  <nav class="px-4 flex flex-col md:flex-row flex-wrap justify-between mt-0 py-1 bg-accent text-back dark:text-front">
    <div class="flex items-center">
      <i class="cursor-pointer glyph fa-bars fa-lg pt-1 mr-4 md:hidden" @click="collapsed = !collapsed"></i>
      
      <i class="cursor-pointer fa fa-lg mr-2" :class="treeOpen ? 'fa-list-alt' : 'fa-list-ul'"
        @click="$emit('toggle-tree', !treeOpen)"></i>
      <node-label oc="person" :dn="user" @select-dn="$emit('select-dn', $event)" class="text-lg" />
    </div>

    <div class="flex items-center space-x-4 text-lg" v-show="!collapsed">
      <!-- Right aligned nav items -->      
      <span class="cursor-pointer" @click="$emit('show-modal', 'ldif-import')">Import…</span>
      
      <dropdown-menu title="Schema">
        <li role="menuitem" v-for="obj in schema.objectClasses._objects"
          :key="obj.name" @click="$emit('display-oc', obj.name)">
            {{ obj.name }}
        </li>
      </dropdown-menu>

      <form @submit.prevent="search">
        <input class="glyph px-2 py-1 rounded border border-front/80 outline-none dark:bg-gray-800/80"
          autofocus :placeholder="' \uf002'" name="q" @focusin="$refs.q.select();"
          @keyup.esc="$refs.q.value = ''; query = '';" id="nav-search" ref="q" />
        <search-results for="nav-search" @select-dn="query = ''; $emit('select-dn', $event);"
          :shorten="baseDn" :query="query" :warning="showWarning" />
      </form>
    </div>

  </nav>
</template>

<script>
  import DropdownMenu from './DropdownMenu.vue';
  import NodeLabel from './NodeLabel.vue';
  import SearchResults from './SearchResults.vue';

  export default {
    name: 'NavBar',

    components: {
      DropdownMenu,
      NodeLabel,
      SearchResults,
    },

    props: {
      dn: String,
      baseDn: String,
      user: String,
      showWarning: Function,
      treeOpen: Boolean,
      schema: Object,
    },

    model: {
      prop: 'treeOpen',
      event: 'toggle-tree',
    },

    data: function() {
      return {
        query: '',
        collapsed: false,
      }
    },

    methods: {
      search: function() {
        const q = this.$refs.q.value;
        this.query = '';
        this.$nextTick(() => { this.query = q; });
      },
    },
  }
</script>
