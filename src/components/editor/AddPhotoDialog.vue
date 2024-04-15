<template>
  <modal title="Upload photo" hide-footer :return-to="returnTo"
    :open="modal == 'add-' + attr"
    @shown="upload?.focus()" @cancel="emit('update:modal')">

    <input name="photo" type="file" ref="upload" @change="onOk"
      :accept="attr == 'jpegPhoto' ? 'image/jpeg' : 'image/*'" />
  </modal>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import Modal from '../ui/Modal.vue';

  const props = defineProps({
      dn: { type: String, required: true },
      attr: {
        type: String,
        validator: (value: string) => ['jpegPhoto', 'thumbnailPhoto'].includes(value),
      },
      modal: String,
      returnTo: String,
    }),
    upload = ref<HTMLInputElement | null>(null),
    emit = defineEmits(['ok', 'update:modal']);

  // add an image
  async function onOk(evt: Event) {
    const target = evt.target as HTMLInputElement;
    if (!target?.files) return;
    
    const fd = new FormData();
    fd.append('blob', target.files[0])
    const response = await fetch('api/blob/' + props.attr + '/0/' + props.dn, {
      method: 'PUT',
      body: fd,
    });
    
    if (response.ok) {
      emit('update:modal');
      emit('ok', props.dn, [props.attr]);
    }
  }
</script>
