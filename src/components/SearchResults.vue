<template>
  <popover :target="elementId" v-if="show" :open="show" @close="clear">
    <li v-for="item in results" :key="item.dn" @click="done(item.dn)"
      :title="label == 'dn' ? '' : trim(item.dn)" role="menuitem">
        {{ item[label] }}
    </li>
  </popover>
</template>

<script>
  import Popover from './Popover.vue';

  export default {
    name: 'SearchResults',

    components: {
      Popover,
    },

    props: {
      query: String,
      for: String,

      label: {
        type: String,
        default: 'name',
        validator: value => ['name', 'dn' ].includes(value)
      },

      shorten: String,
      warning: Function,
    },

    data: function() {
      return {
        results: [],
        popup: null,
      }
    },

    inject: [ 'xhr' ],

    watch: {
      
      query: async function(q) {
        if (!q) return;

        this.clear();
        this.results = await this.xhr({ url: 'api/search/' + q });
        if (!this.results) return; // XHR failed

        if (this.results.length == 0) {
          if (this.warning) this.warning('No search results');
          return;
        }

        if (this.results.length == 1) {
          this.done(this.results[0].dn);
          return;
        }

        this.results.sort((a, b) =>
          a[this.label].toLowerCase().localeCompare(
            b[this.label].toLowerCase()));
      },
    },

    methods: {

      trim: function(dn) {
        return this.shorten && this.shorten != dn
          ? dn.replace(this.shorten, '…') : dn;
      },

      // use an auto-completion choice
      done: function(dn) {
        this.$emit('select-dn', dn);
        this.clear();

        // Return focus to search input
        this.$nextTick(function() {
          const el = document.getElementById(this.for);
          if (el) el.focus();
        });
      },

      clear: function() {
        this.results = [];
      },
    },

    computed: {
      elementId: function() { // alias "for" prop for templates
        return this.for;
      },

      show: function() {
        return this.query && this.results && this.results.length > 1;
      },
    }

  }
</script>
