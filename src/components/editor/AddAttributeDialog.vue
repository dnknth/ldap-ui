<template>
  <modal title="Add attribute" :open="modal == 'add-attribute'" :return-to="props.returnTo" @show="attr = undefined"
    @shown="select?.focus()" @ok="onOk" @cancel="emit('update:modal')">
    <select v-model="attr" ref="select" @keyup.enter="onOk">
      <option v-for="attr in available" :key="attr">{{ attr }}</option>
    </select>
  </modal>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Modal from "../ui/Modal.vue";
import type { Entry } from "../../generated/types.gen";

const props = defineProps<{
  entry: Entry;
  attributes: string[];
  modal?: string;
  returnTo?: string;
}>(),
  attr = ref<string>(),
  select = ref<HTMLSelectElement | undefined>(undefined),
  available = computed(() =>
    // Choice list for new attribute selection popup
    props.attributes.filter(
      (attr) => !Object.keys(props.entry.attrs).includes(attr))
  ),
  emit = defineEmits<{
    ok: [attr: string];
    "show-modal": [name: string];
    "update:modal": [name?: string];
  }>();

// Add the selected attribute
function onOk() {
  if (!attr.value) return;

  if (attr.value == "jpegPhoto" || attr.value == "thumbnailPhoto") {
    emit("show-modal", "add-" + attr.value);
    return;
  }

  if (attr.value == "userPassword") {
    emit("show-modal", "change-password");
    return;
  }

  emit("update:modal");
  emit("ok", attr.value);
}
</script>
