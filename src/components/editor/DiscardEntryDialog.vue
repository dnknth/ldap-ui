<template>
  <b-modal id="confirm-discard" title="Are you sure?" @show="init" @ok="done"
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
    entry: {
      type: Object,
      required: true,
    },
    dn: String,
  },

  model: {
    prop: 'entry',
    event: 'form-changed',
  },

  data: function() {
    return {
      back: undefined,
    };
  },

  methods: {

    init: function() {
      this.back = this.dn;
      this.$emit('select-dn');
    },

    done: function() {
      this.$emit('form-changed', null);
      this.$emit('select-dn', this.back);
    },
  },
}
</script>
