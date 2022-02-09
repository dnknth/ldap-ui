<template>
  <b-popover :target="elementId" :show="show" v-if="show" :placement="placement">
    <div class="search-results">
      <div v-for="item in results" :key="item.dn" @click="done(item.dn)"
        :title="label == 'dn' ? '' : item.dn">
          {{ display(item) }}
      </div>
    </div>
  </b-popover>
</template>

<script>

export default {

  name: 'SearchResults',

  props: {
    query: String,

    for: {
      type: String,
      required: true,
    },

    placement: {
      type: String,
      default: 'bottom',
    },

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
      this.results = [];
      if (!q) return;

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

    display: function(item) {
      let label = item[this.label];
      if (this.shorten && this.shorten != label) {
        label = label.replace(this.shorten, '…');
      }
      return label;
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
      return this.results && this.results.length > 1;
    },
  }

}
</script>

<style>
  .b-popover .popover-body {
    background-color: var(--muted-bg);
    color: var(--muted-fg);
    border: 1px solid var(--accent);
    border-radius: 4px;
  }

  .search-results {
    padding-left: 0px;
    padding-inline-start: 0px !important;
  }

  .search-results div {
    list-style-type: none;
    cursor: pointer;
  }

  .search-results div:hover {
    color: var(--body-fg);
  }
</style>
