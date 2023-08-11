<template>
  <modal title="Add objectClass" :open="modal == 'add-object-class'"
    @show="oc = null;" @shown="$refs.oc.focus()"
    @ok="onOk" @cancel="$emit('update:modal')">
    
    <select v-model="oc" ref="oc" @keyup.enter="onOk">
      <option v-for="cls in available" :key="cls">{{ cls }}</option>
    </select>
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'AddObjectClassDialog',

    components: {
      Modal,
    },

    props: {
      entry: Object,
      modal: String,
    },

    data: function() {
      return {
        oc: null,
      };
    },

    methods: {
      onOk: function() {
        if (this.oc) {
          this.$emit('update:modal');
          this.$emit('ok', this.oc);
        }
      },
    },
    
    computed: {
      available: function() {
        const classes = this.entry.attrs.objectClass;
        return this.entry.meta.aux.filter(cls => !classes.includes(cls));
      },
    },
  }
</script>
