<template>
  <ul :id="attr + '-dropdown'" class="hidden dropdown">
    <li v-for="item in results" class="clickable dropdown-item" :key="item.dn"
      @click="pick">{{ item.dn }}
    </li>
  </ul>
</template>

<script>

import { createPopper } from '@popperjs/core';

export default {

  name: 'AutoCompletion',

  props: {
    attr: {
      type: String,
      required: true,
    },
    values: {
      type: Array,
      required: true,
    },
    index: Number,
    query: String,
  },

  model: {
    prop: 'values',
    event: 'auto-complete',
  },

  data: function() {
    return {
      results: [],
      dropdown: null,  // <ul> with completions
    }
  },

  inject: [ 'xhr' ],

  watch: {
    
    query: async function(q) {
      if (!q) {
        this.clear();
        return;
      }

      this.results = await this.xhr({ url: 'api/search/' + q }) || [];

      if (this.results.length == 0) {
        this.clear();
        return;
      }

      const dropdown = document.getElementById(this.attr + '-dropdown');
      if (this.results.length) {
        dropdown.className = 'dropdown';
        this.dropdown = createPopper(
          document.getElementById(this.attr + '-' + this.index),
          dropdown, {
            modifiers: [ {
              name: 'offset',
              options: { offset: [0, -2] },
            } ]
        });
        dropdown.setAttribute('data-show', '');
      }
    },
  },

  beforeDestroy: function() { this.clear(); },

  methods: {

    // use an auto-completion choice
    pick: function(evt) {
      const dropdownId = this.attr + '-' + this.index;
      const el = document.getElementById(dropdownId);
      this.values[this.index] = evt.target.innerText;
      this.$emit('auto-complete', this.values);

      this.$nextTick(function() { if (el) el.focus(); });
      this.clear();
    },
    
    clear: function() {
      if (this.dropdown) this.dropdown.destroy();
      this.dropdown = null;
      this.results = [];
      const dropdown = document.getElementById(this.attr + '-dropdown');
      if (dropdown) {
        dropdown.removeAttribute('data-show');
        dropdown.className = 'hidden';
      }
    },
  },

}
</script>

<style scoped>
  ul.dropdown {
    padding: 0.3em;
    border: 1px solid var(--accent);
    border-radius: 8px;
    z-index: 99;
    box-shadow: 2px 2px 2px 0 rgba(0,0,0,0.3);
    list-style-type: none;
    background-color: var(--muted-bg);
  }

  ul.dropdown li {
    padding: 0 0.5em;
    cursor: pointer;
    color: var(--muted-fg);
    background-color: var(--muted-bg);
  }

  ul.dropdown li:hover {
    color: var(--body-fg);
  }
</style>
