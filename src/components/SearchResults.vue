<template>
  <popover :open="show" @update:open="results = []">
    <li v-for="item in results" :key="item.dn" @click="done(item.dn)"
      :title="label == 'dn' ? '' : trim(item.dn)" role="menuitem">
        {{ item[label] }}
    </li>
  </popover>
</template>

<script>
  import Popover from './ui/Popover.vue';

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
      silent: {
        type: Boolean,
        default: false,
      },
    },

    data: function() {
      return {
        results: [],
      };
    },

    inject: [ 'app' ],

    watch: {
      
      query: async function(q) {
        if (!q) return;

        this.results = await this.app.xhr({ url: 'api/search/' + q });
        if (!this.results) return; // app.xhr failed

        if (this.results.length == 0 && !this.silent) {
          this.app.showWarning('No search results');
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
        this.results = [];

        this.$nextTick(function() {
          // Return focus to search input
          const el = document.getElementById(this.for);
          if (el) el.focus();
        });
      },
    },

    computed: {
      show: function() {
        return this.query.trim() != ''
          && this.results && this.results.length > 1;
      },
    }

  }
</script>
