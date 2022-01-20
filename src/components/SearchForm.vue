<template>
  <b-nav-form @submit.prevent="search">
    <input size="sm" class="mr-sm-2 form-control" id="search"
      :placeholder="'\uf002'" name="q" onClick="this.select();" />

    <div id="search-popup" class="hidden">
      <div id="arrow" data-popper-arrow></div>
      <ul>
        <li v-for="entry in results" class="clickable search-item"
          :key="entry.dn" @click="$emit('select-dn', entry.dn)">{{ entry.name }}
        </li>
      </ul>
    </div>     
  </b-nav-form>
</template>

<script>
import { createPopper } from '@popperjs/core';

export default {

  name: 'SearchForm',

  props: {
    dn: String,
    showWarning: {
      type: Function,
      required: true,
    },
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      results: null,
      popup: null,
    }
  },

  watch: {
    dn: function() { this.clear() },
  },

  methods: {

    search: async function() {
      this.clear();
      const q = document.getElementById('search').value;
      if (!q) return;

      const response = await this.xhr({ url: 'api/search/' + q });
      if (!response) return;
      
      if (!response.length) {
        this.showWarning('No search results');
        return;
      }

      if (response.length == 1) {
        this.$emit('select-dn', response[0].dn);
        return;
      }

      // multiple results
      this.results = response;
      const popup = document.getElementById('search-popup');
      popup.className = '';
      this.popup = createPopper(
        document.getElementById('search'),
        popup, {
          modifiers: [ {
            name: 'offset',
            options: { offset: [0, 4] },
          } ]
        });
        popup.setAttribute('data-show', '');
    },

    clear: function() {
      this.popup = this.results = null;
      if (this.popup) this.popup.destroy();
      this.hide();
    },

    hide: function() {
      const popup = document.getElementById('search-popup');
      if (popup) {
        popup.removeAttribute('data-show');
        popup.className = 'hidden';
      }
    },

  },
}
</script>

<style>
  #search {
    font-family: sans-serif, FontAwesome;
  }

  #arrow, #arrow::before {
    position: absolute;
    width: 8px;
    height: 8px;
    z-index: -1;
  }

  #arrow::before {
    content: '';
    transform: rotate(45deg);
    background-color: var(--body-bg);
  }

  #search-popup[data-popper-placement^='bottom'] > #arrow {
    top: -4px;
  }

  #search-popup {
    border: 1px solid var(--accent);
    border-radius: 4px;
    z-index: 99;
    background-color: var(--muted-bg);
    box-shadow: 2px 2px 2px 0 rgba(0,0,0,0.3);
  }

  #search-popup ul {
    list-style-type: none;
    padding: 0.3em;
  }

  #search-popup li {
    padding: 0 0.5em;
    color: var(--muted-fg);
  }

  #search-popup li:hover {
    color: var(--body-fg);
    cursor: pointer;
  }

  @media (prefers-color-scheme: dark) {
  }
</style>
