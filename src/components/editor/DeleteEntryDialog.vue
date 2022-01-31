<template>
  <b-modal id="confirm" title="Are you sure?" @show="reset" @shown="init" @ok="done"
    cancel-variant="primary" ok-variant="danger">

    <p class="strong">This action is irreversible.</p>

    <div v-if="subtree &amp;&amp; subtree.length">
      <p class="red">The following child nodes will be also deleted:</p>
      <div v-for="node in subtree" :key="node.dn">
        <span v-for="i in node.level" class="indent" :key="i"></span>
        <node-label :oc="node.structuralObjectClass">
          {{ node.dn.split(',')[0] }}
        </node-label>
      </div>
    </div>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Delete
    </template>
  </b-modal>
</template>

<script>

import NodeLabel from '../NodeLabel.vue'

export default {

  name: 'DeleteEntryDialog',

  components: {
    NodeLabel,
  },

  props: {
    dn: {
      type: String,
      required: true,
    },
    info: {
      type: Function,
      required: true,
    },
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      subtree: [],
    }
  },

  methods: {

    reset: function() {
      this.subtree = [];
    },

    // List subordinate elements of a DN
    init: async function() {
      this.subtree = await this.xhr({ url:  'api/subtree/' + this.dn});
    },

    done: async function() {
      if (await this.xhr({ url: 'api/entry/' + this.dn, method: 'DELETE' }) !== undefined) {
        this.info('Deleted entry: ' + this.dn);
        this.$emit('select-dn', '-' + this.dn);
      }
    },
  },
}
</script>

<style scoped>

  .red {
    color: red !important;
  }

  span.indent {
    margin-left: 1.2em;
  }

</style>
