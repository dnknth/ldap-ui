<template>
  <modal title="Are you sure?" :open="modal == 'discard-entry'" :return-to="returnTo" cancel-classes="bg-primary/80"
    ok-classes="bg-danger/80" @show="next = dn" @shown="onShown" @ok="onOk" @cancel="emit('update:modal')">
    <p class="strong">All changes will be irreversibly lost.</p>

    <template #modal-ok> <i class="fa fa-trash-o fa-lg"></i> Discard </template>
  </modal>
</template>

<script setup lang="ts">
import { ref } from "vue";
import Modal from "../ui/Modal.vue";

defineProps<{
  dn?: string;
  modal?: string;
  returnTo?: string;
}>();

const next = ref<string>(),
  emit = defineEmits<{
    ok: [next?: string];
    shown: [];
    "update:modal": [];
  }>();

function onShown() {
  document.getElementById("ui-modal-ok")?.focus();
  emit("shown");
}

function onOk() {
  emit("update:modal");
  emit("ok", next.value);
}
</script>
