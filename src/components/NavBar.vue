<template>
  <b-navbar toggleable="md" type="dark" variant="info">
    <b-navbar-toggle target="nav_collapse" />
    
    <b-navbar-brand>
      <i class="clickable fa" :class="treeOpen ? 'fa-list-alt' : 'fa-list-ul'"
        @click="$emit('toggle-tree', !treeOpen)"></i>
      <node-label oc="person" :dn="user" cssClass="clickable"
        @select-dn="$emit('select-dn', $event)" />
    </b-navbar-brand>

    <b-collapse is-nav id="nav_collapse">
      <b-navbar-nav class="ml-auto"><!-- Right aligned nav items -->
      
        <b-nav-item v-b-modal.ldif-import>Import…</b-nav-item>
        
        <b-nav-item-dropdown text="Schema" right>
          <b-dropdown-item v-for="obj in schema.objectClasses._objects"
            :key="obj.name" @click="$emit('display-oc', obj.name)">
              {{ obj.name }}
          </b-dropdown-item>
        </b-nav-item-dropdown>

        <b-nav-form @submit.prevent="query = search">
          <input size="sm" class="glyph mr-sm-2 form-control" id="search" v-model="search"
            :placeholder="'\uf002'" name="q" onClick="this.select();" @keyup.esc="query = ''" />
          <search-results for="search" @select-dn="query = ''; $emit('select-dn', $event)"
            :shorten="baseDn" :query="query" :warning="showWarning" placement="bottomleft" />
        </b-nav-form>

      </b-navbar-nav>
    </b-collapse>
  </b-navbar>
</template>

<script>

import NodeLabel from './NodeLabel.vue';
import SearchResults from './SearchResults.vue';

export default {

  name: 'NavBar',

  components: {
    NodeLabel,
    SearchResults,
  },

  props: {
    dn: String,
    baseDn: String,
    user: String,

    showWarning: {
      type: Function,
      required: true,
    },

    treeOpen: {
      type: Boolean,
      required: true,
    },

    schema: {
      type: Object,
      required: true,
    },
  },

  model: {
    prop: 'treeOpen',
    event: 'toggle-tree',
  },

  data: function() {
    return {
      query: '',
      search: '',
    }
  },

  watch: {
    dn: function() { this.query = ''; },
    search: function(q) { if (!q) this.query = ''; },
  },

}
</script>

<style>
  @media (prefers-color-scheme: dark) {
    .navbar-dark .navbar-toggler {
      border-color: var(--muted-fg);
    }

    .navbar-toggler-icon {
      background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' width='30' height='30' viewBox='0 0 30 30'%3e%3cpath stroke='rgba%28255, 255, 255%29' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e") !important;
    }
  }

  .navbar-brand i.fa-list-alt, .navbar-brand i.fa-list-ul {
    margin-right: 1em;
  }

  .navbar-dark .navbar-nav .nav-link {
    color: white;
  }

  a.nav-link {
    padding-right: 0;
  }

</style>
