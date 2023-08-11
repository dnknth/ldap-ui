<template>
  <modal title="Add attribute" :open="modal == 'add-attribute'"
    @show="attr = null;" @shown="$refs.attr.focus()"
    @ok="onOk" @cancel="$emit('update:modal')">

    <select v-model="attr" ref="attr" @keyup.enter="onOk">
      <option v-for="attr in available" :key="attr">{{ attr }}</option>
    </select>
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'AddAttributeDialog',

    components: {
      Modal,
    },

    props: {
      entry: Object,
      attributes: Array,
      modal: String,
    },

    data: function() {
      return {
        attr: null,
      };
    },

    methods: {
      // Add the selected attribute
      onOk: function() {
        if (!this.attr) return;

        if (this.attr == 'jpegPhoto' || this.attr == 'thumbnailPhoto') {
          this.$emit('show-modal', 'add-' + this.attr);
          return;
        }
        
        if (this.attr == 'userPassword') {
          this.$emit('show-modal', 'change-password');
          return;
        }
        
        this.$emit('update:modal');
        this.$emit('ok', this.attr);
      },
    },
              
    computed: {
      // Choice list for new attribute selection popup
      available: function() {
        const attrs = Object.keys(this.entry.attrs);
        return this.attributes.filter(attr => !attrs.includes(attr));
      },
    },
  }
</script>
