<template>
  <modal title="Are you sure?" :open="modal == 'discard-entry'"
    cancel-variant="primary" ok-variant="danger"
    @show="next = dn;" @shown="$emit('shown')"
    @ok="onOk" @cancel="$emit('update:modal')">

    <p class="strong">All changes will be irreversibly lost.</p>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Discard
    </template>
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'DiscardEntryDialog',

    components: {
      Modal,
    },

    props: {
      dn: String,
      modal: String,
    },

    data: function() {
      return {
        next: undefined,
      };
    },

    methods: {
      onOk: function() {
        this.$emit('update:modal');
        this.$emit('ok', this.next);
      },
    },
  }
</script>
