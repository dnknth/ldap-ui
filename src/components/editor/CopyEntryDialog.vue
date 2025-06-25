<template>
  <modal title="Copy entry" :open="modal == 'copy-entry'" :return-to="returnTo" @show="init" @shown="newdn?.focus()"
    @ok="onOk" @cancel="emit('update:modal')">
    <div>
      <div class="text-danger text-xs mb-1" v-if="error">{{ error }}</div>
      <input ref="newdn" v-model="dn" placeholder="New DN" @keyup.enter="onOk" />
    </div>
  </modal>
</template>

<script setup lang="ts">
import { ref } from "vue";
import Modal from "../ui/Modal.vue";
import type { Entry } from "../../generated/types.gen";

const props = defineProps<{
  entry: Entry;
  modal?: string;
  returnTo?: string;
}>(),
  emit = defineEmits<{
    ok: [entry: Entry];
    "update:modal": [];
  }>(),
  dn = ref(""),
  error = ref(""),
  newdn = ref<HTMLInputElement | null>(null);

function init() {
  error.value = "";
  dn.value = props.entry.dn;
}

// Load copied entry into the editor
function onOk() {
  if (!dn.value || dn.value == props.entry.dn) {
    error.value = "This DN already exists";
    return;
  }

  const parts = dn.value.split(","),
    rdnpart = parts[0].split("="),
    rdn = rdnpart[0];

  if (rdnpart.length != 2) {
    error.value = "Invalid RDN: " + parts[0];
    return;
  }

  emit("update:modal");
  const entry = JSON.parse(JSON.stringify(props.entry));
  entry.attrs[rdn] = [rdnpart[1]];
  entry.dn = dn.value;
  entry.isNew = true;
  emit("ok", entry);
}
</script>
