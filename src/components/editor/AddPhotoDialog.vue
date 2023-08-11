<template>
  <modal title="Upload photo" hide-footer :open="modal == 'add-' + attr"
    @shown="$refs.upload.focus()" @cancel="$emit('update:modal')">

    <input name="photo" type="file" ref="upload" @change="onOk"
      :accept="attr == 'jpegPhoto' ? 'image/jpeg' : 'image/*'" />
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'AddPhotoDialog',

    components: {
      Modal,
    },

    props: {
      dn: String,
      attr: {
        type: String,
        validator: value => ['jpegPhoto', 'thumbnailPhoto' ].includes(value),
      },
      modal: String,
    },

    inject: [ 'app' ],

    methods: {
      // add an image
      onOk: async function(evt) {
        if (!evt.target.files) return;
        
        const fd = new FormData();
        fd.append('blob', evt.target.files[0])
        const data = await this.app.xhr({
          url:  'api/blob/' + this.attr + '/0/' + this.dn,
          method: 'PUT',
          data: fd,
          binary: true,
        });

        if (data) {
          this.$emit('update:modal');
          this.$emit('ok', this.dn, data.changed);
        }
      },
    },
  }
</script>
