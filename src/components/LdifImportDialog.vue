<template>
  <modal title="Import" :open="modal == 'ldif-import'" ok-title="Import"
    @show="init" @ok="onOk" @cancel="emit('update:modal')">
      <textarea v-model="ldifData" id="ldif-data" placeholder="Paste or upload LDIF"></textarea>
      <input type="file" @change="upload" accept=".ldif" />
  </modal>
</template>

<script setup>
  import { inject, ref } from 'vue';
  import Modal from './ui/Modal.vue';

  const
    app = inject('app'),
    ldifData = ref(''),
    ldifFile = ref(null),
    emit = defineEmits(['ok', 'update:modal']);

  defineProps({ modal: String });
  
  function init() {
    ldifData.value = '';
    ldifFile.value = null;
  }
  
  // Load LDIF from file
  function upload(evt) {
    const file = evt.target.files[0],
      reader = new FileReader();

    reader.onload = function() {
      ldifData.value = reader.result;
      evt.target.value = null;
    }
    reader.readAsText(file);
  }
  
  // Import LDIF
  async function onOk() {
    if (!ldifData.value) return;

    emit('update:modal');
    const data = await app.xhr({
      url: 'api/ldif',
      method: 'POST',
      data: ldifData.value,
    });

    if (data) emit('ok');
  }
</script>
