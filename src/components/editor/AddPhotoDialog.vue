<template>
  <modal title="Upload photo" hide-footer :return-to="returnTo"
    :open="modal == 'add-' + attr"
    @shown="upload.focus()" @cancel="emit('update:modal')">

    <input name="photo" type="file" ref="upload" @change="onOk"
      :accept="attr == 'jpegPhoto' ? 'image/jpeg' : 'image/*'" />
  </modal>
</template>

<script setup>
  import { ref, inject } from 'vue';
  import Modal from '../ui/Modal.vue';

  const props = defineProps({
      dn: { type: String, required: true },
      attr: {
        type: String,
        validator: value => ['jpegPhoto', 'thumbnailPhoto'].includes(value),
      },
      modal: String,
      returnTo: String,
    }),
    app = inject('app'),
    upload = ref('upload'),
    emit = defineEmits(['ok', 'update:modal']);

  // add an image
  async function onOk(evt) {
    if (!evt.target.files) return;
    
    const fd = new FormData();
    fd.append('blob', evt.target.files[0])
    const data = await app.xhr({
      url:  'api/blob/' + props.attr + '/0/' + props.dn,
      method: 'PUT',
      data: fd,
      binary: true,
    });

    if (data) {
      emit('update:modal');
      emit('ok', props.dn, data.changed);
    }
  }
</script>
