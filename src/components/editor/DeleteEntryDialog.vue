<template>
  <modal title="Are you sure?" :open="modal == 'delete-entry'"
    cancel-variant="primary" ok-variant="danger"
    @show="init" @ok="onOk" @cancel="$emit('close')">

    <p class="strong">This action is irreversible.</p>

    <div v-if="subtree && subtree.length">
      <p class="text-danger mb-2">The following child nodes will be also deleted:</p>
      <div v-for="node in subtree" :key="node.dn">
        <span v-for="i in node.level" class="ml-6" :key="i"></span>
        <node-label :oc="node.structuralObjectClass">
          {{ node.dn.split(',')[0] }}
        </node-label>
      </div>
    </div>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Delete
    </template>
  </modal>
</template>

<script>
  import Modal from '../Modal.vue';
  import NodeLabel from '../NodeLabel.vue';

  export default {
    name: 'DeleteEntryDialog',

    components: {
      Modal,
      NodeLabel,
    },

    props: {
      dn: String,
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    inject: [ 'xhr' ],

    data: function() {
      return {
        subtree: [],
      }
    },

    methods: {
      // List subordinate elements to be deleted
      init: async function() {
        this.subtree = await this.xhr({ url: 'api/subtree/' + this.dn}) || [];
      },

      onOk: function() {
        this.$emit('close');
        this.$emit('ok', this.dn);
      },
    },
  }
</script>
