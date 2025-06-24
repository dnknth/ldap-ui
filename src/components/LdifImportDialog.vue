<template>
  <modal title="Import" :open="modal == 'ldif-import'" ok-title="Import" @show="init" @ok="onOk"
    @cancel="emit('update:modal')">
    <textarea v-model="ldifData" id="ldif-data" placeholder="Paste or upload LDIF"></textarea>
    <input type="file" @change="upload" accept=".ldif" />
  </modal>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Modal from './ui/Modal.vue';
import { postLdif } from '../generated/sdk.gen'

const
  ldifData = ref(''),
  emit = defineEmits<{
    ok: []
    'update:modal': []
  }>();

defineProps<{ modal?: string }>();

function init() {
  ldifData.value = '';
}

// Load LDIF from file
function upload(evt: Event) {
  const target = evt.target as HTMLInputElement,
    files = target.files as FileList,
    file = files[0],
    reader = new FileReader();

  reader.onload = function () {
    ldifData.value = reader.result as string;
    target.value = '';
  }
  reader.readAsText(file);
}

// Import LDIF
async function onOk() {
  if (!ldifData.value) return;

  emit('update:modal');
  const response = await postLdif({ body: ldifData.value });
  if (!response.error) emit('ok');
}
</script>
