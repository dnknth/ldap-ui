<template>
  <modal title="Are you sure?" :open="modal == 'discard-entry'"
    cancel-variant="primary" ok-variant="danger"
    @show="next = dn;" @shown="$emit('shown')"
    @ok="onOk" @cancel="$emit('close')">

    <p class="strong">All changes will be irreversibly lost.</p>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Discard
    </template>
  </modal>
</template>

<script>
  import Modal from '../Modal.vue';

  export default {
    name: 'DiscardEntryDialog',

    components: {
      Modal,
    },

    props: {
      dn: String,
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    data: function() {
      return {
        next: undefined,
      }
    },

    methods: {
      onOk: function() {
        this.$emit('close');
        this.$emit('ok', this.next);
      },
    },
  }
</script>
