<template>
  <b-modal id="confirm-discard" title="Are you sure?" @shown="init" @ok="done"
    @cancel="$emit('select-dn')" cancel-variant="primary" ok-variant="danger">

    <p class="strong">All changes will be irreversibly lost.</p>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Discard
    </template>
  </b-modal>
</template>

<script>

export default {

  name: 'DiscardEntryDialog',

  props: {
    dn: String,
  },

  data: function() {
    return {
      next: undefined,
    }
  },

  methods: {

    init: function() {
      this.next = this.dn;
      this.$emit('select-dn');
    },

    done: function() {
      this.$emit('replace-entry', null);
      this.$emit('select-dn', this.next);
    },
  },
}
</script>
