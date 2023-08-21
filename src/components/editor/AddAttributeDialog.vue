<template>
  <modal title="Add attribute" :open="modal == 'add-attribute'" :return-to="props.returnTo"
    @show="attr = null;" @shown="select.focus()"
    @ok="onOk" @cancel="emit('update:modal')">

    <select v-model="attr" ref="select" @keyup.enter="onOk">
      <option v-for="attr in available" :key="attr">{{ attr }}</option>
    </select>
  </modal>
</template>

<script setup>
  import { computed, ref } from 'vue';
  import Modal from '../ui/Modal.vue';

  const props = defineProps({
      entry: { type: Object, required: true },
      attributes: { type: Array, required: true },
      modal: String,
      returnTo: String,
    }),
    attr = ref(null),
    select = ref(null),
    available = computed(() => {
      // Choice list for new attribute selection popup
      const attrs = Object.keys(props.entry.attrs);
      return props.attributes.filter(attr => !attrs.includes(attr));
    }),
    emit = defineEmits(['ok', 'show-modal', 'update:modal']);

  // Add the selected attribute
  function onOk() {
    if (!attr.value) return;

    if (attr.value == 'jpegPhoto' || attr.value == 'thumbnailPhoto') {
      emit('show-modal', 'add-' + attr.value);
      return;
    }
    
    if (attr.value == 'userPassword') {
      emit('show-modal', 'change-password');
      return;
    }
    
    emit('update:modal');
    emit('ok', attr.value);
  }
</script>
