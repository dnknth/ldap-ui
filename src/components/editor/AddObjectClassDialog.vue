<template>
  <modal title="Add objectClass" :open="modal == 'add-object-class'" @show="oc = undefined" @shown="select?.focus()"
    @ok="onOk" @cancel="emit('update:modal')">
    <select v-model="oc" ref="select" @keyup.enter="onOk">
      <option v-for="cls in available" :key="cls">{{ cls }}</option>
    </select>
  </modal>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import Modal from "../ui/Modal.vue";
import type { Entry } from "../../generated/types.gen";
import type { Provided } from "../Provided";

const props = defineProps<{
  entry: Entry;
  modal?: string;
}>(),
  emit = defineEmits<{
    ok: [oc: string];
    "update:modal": [];
  }>(),
  app = inject<Provided>("app"),
  oc = ref<string>(),
  select = ref<HTMLSelectElement | null>(),
  available = computed(() =>
    Array.from(app?.schema.objectClasses.values() || [])
      .filter(
        (oc) => oc.aux && !props.entry.attrs.objectClass.includes(oc.name!),
      )
      .map((oc) => oc.name),
  );

function onOk() {
  if (oc.value) {
    emit("update:modal");
    emit("ok", oc.value);
  }
}
</script>
