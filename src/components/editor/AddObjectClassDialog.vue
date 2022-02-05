<template>
  <b-modal id="add-oc" title="Add objectClass"
    @show="reset" @shown="init" @ok="done" @hidden="$emit('update-form')">
    
    <b-form-select v-model="oc" id="oc-select" class="mb-3" :options="available"
      @keydown.native.enter.prevent="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'AddObjectClassDialog',

  props: {
    entry: {
      type: Object,
      required: true,
    },
  },

  data: function() {
    return {
      oc: null,
    }
  },

  methods: {

    reset: function() {
      this.oc = null;
    },

    init: function() {
      document.getElementById('oc-select').focus();
    },

    done: function() {
      this.entry.attrs.objectClass.push(this.oc);
      this.$bvModal.hide('add-oc');
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
