<template>
  <modal title="Add objectClass" :open="modal == 'add-object-class'" @show="oc = undefined;" @shown="select?.focus()"
    @ok="onOk" @cancel="emit('update:modal')">

    <select v-model="oc" ref="select" @keyup.enter="onOk">
      <option v-for="cls in available" :key="cls">{{ cls }}</option>
    </select>
  </modal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import Modal from '../ui/Modal.vue';

const props = defineProps({
  entry: { type: Object, required: true },
  modal: String,
}),
  oc = ref<string>(),
  select = ref<HTMLSelectElement | null>(),
  available = computed<string[]>(() => {
    const classes = props.entry.attrs.objectClass;
    return props.entry.meta.aux.filter((cls: string) => !classes.includes(cls));
  }),
  emit = defineEmits(['ok', 'update:modal']);

function onOk() {
  if (oc.value) {
    emit('update:modal');
    emit('ok', oc.value);
  }
}
</script>
