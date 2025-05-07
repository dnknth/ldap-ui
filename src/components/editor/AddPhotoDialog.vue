<template>
  <modal title="Upload photo" hide-footer :return-to="returnTo" :open="modal == 'add-' + attr" @shown="upload?.focus()"
    @cancel="emit('update:modal')">

    <input name="photo" type="file" ref="upload" @change="onOk"
      :accept="attr == 'jpegPhoto' ? 'image/jpeg' : 'image/*'" />
  </modal>
</template>

<script setup lang="ts">
import { ref, inject } from 'vue';
import Modal from '../ui/Modal.vue';
import { putBlob } from '../../generated/sdk.gen'
import type { Provided } from '../Provided'

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
  emit = defineEmits(['ok', 'update:modal']),
  app = inject<Provided>('app');

// add an image
async function onOk(evt: Event) {
  const target = evt.target as HTMLInputElement;
  if (!target?.files) return;

  const response = await putBlob({
    path: { attr: props.attr!, index: 0, dn: props.dn },
    body: { blob: target.files[0] },
    client: app?.client
  });

  if (!response.error) {
    emit('update:modal');
    emit('ok', props.dn, [props.attr]);
  }
}
</script>
