<template>
  <b-modal id="add-attribute" title="Add attribute"
    @show="reset" @shown="init" @ok="done" @hidden="focus">

    <b-form-select v-model="attr" id="new-attr" :options="available" class="mb-3"
      @keydown.native.enter.prevent="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'AddAttributeDialog',

  props: {
    entry: {
      type: Object,
      required: true,
    },
    attributes: {
      type: Array,
      required: true,
    },
  },

  data: function() {
    return {
      attr: null,
    }
  },

  methods: {

    reset: function() {
      this.attr = null;
    },

    init: function() {
      document.getElementById('new-attr').focus();
    },

    // Add the selected attribute
    done: function(evt) {
      if (!this.attr) {
        evt.preventDefault();
        return;
      }

      this.$bvModal.hide('add-attribute');

      if (this.attr == 'jpegPhoto' || this.attr == 'thumbnailPhoto') {
        this.$bvModal.show('upload-' + this.attr);
        return;
      }
      if (this.attr == 'userPassword') {
        this.$bvModal.show('change-password');
        return;
      }

      const entry = Object.assign({}, this.entry);
      this.$set(entry.attrs, this.attr, ['']);
    },

    focus: function() {
      this.$emit('update-form', this.attr + '-0');
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
