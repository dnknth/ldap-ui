<template>
  <b-modal id="upload-photo" title="Upload photo" @shown="init" hide-footer>
    <input type="file" name="photo" id="add-photo" accept="image/jpeg" @change="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'AddPhotoDialog',

  props: {
    dn: {
      type: String,
      required: true,
    },
  },

  inject: [ 'xhr' ],

  methods: {
    init: function() {
      document.getElementById('add-photo').focus();
    },

    // add an image
    done: async function(evt) {
      if (!evt.target.files) return;
      
      const fd = new FormData();
      fd.append("blob", evt.target.files[0])
      const data = await this.xhr({
        url:  'api/blob/jpegPhoto/0/' + this.dn,
        method: 'PUT',
        data: fd,
        binary: true,
      });

      if (data) this.$emit('select-dn', this.dn, data.changed);
      this.$bvModal.hide('upload-photo');
    },
  },
}
</script>
