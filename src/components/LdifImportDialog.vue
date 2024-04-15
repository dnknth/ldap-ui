<template>
  <modal title="Import" :open="modal == 'ldif-import'" ok-title="Import"
    @show="init" @ok="onOk" @cancel="emit('update:modal')">
      <textarea v-model="ldifData" id="ldif-data" placeholder="Paste or upload LDIF"></textarea>
      <input type="file" @change="upload" accept=".ldif" />
  </modal>
</template>

<script setup lang="ts">
  import { inject, ref } from 'vue';
  import Modal from './ui/Modal.vue';
  import type { Provided } from './Provided';

  const
    app = inject<Provided>('app'),
    ldifData = ref(''),
    emit = defineEmits(['ok', 'update:modal']);

  defineProps({ modal: String });
  
  function init() {
    ldifData.value = '';
  }
  
  // Load LDIF from file
  function upload(evt: Event) {
    const target = evt.target as HTMLInputElement,
      files = target.files as FileList,
      file = files[0],
      reader = new FileReader();

    reader.onload = function() {
      ldifData.value = reader.result as string;
      target.value = '';
    }
    reader.readAsText(file);
  }
  
  // Import LDIF
  async function onOk() {
    if (!ldifData.value) return;

    emit('update:modal');
    const response = await fetch( 'api/ldif', { method: 'POST', body: ldifData.value });
    if (response.ok) emit('ok');
  }
</script>
