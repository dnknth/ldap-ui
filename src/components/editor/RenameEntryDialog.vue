<template>
  <modal
    title="Rename entry"
    :open="modal == 'rename-entry'"
    :return-to="returnTo"
    @ok="onOk"
    @cancel="emit('update:modal')"
    @show="init"
    @shown="select?.focus()"
  >
    <label
      >New RDN attribute:
      <select ref="select" v-model="rdn" @keyup.enter="onOk">
        <option v-for="rdn in rdns" :key="rdn">{{ rdn }}</option>
      </select>
    </label>
  </modal>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from "vue";
import Modal from "../ui/Modal.vue";
import type { Entry } from "@/generated";

const props = defineProps<{
    entry: Entry;
    modal?: string;
    returnTo?: string;
  }>(),
  rdn = ref<string>(),
  select = useTemplateRef("select"),
  rdns = computed(() => Object.keys(props.entry.attrs).filter(ok)),
  emit = defineEmits<{
    ok: [rdn: string];
    "update:modal": [];
  }>();

function init() {
  rdn.value = rdns.value.length == 1 ? rdns.value[0] : undefined;
}

function onOk() {
  const rdnAttr = props.entry.attrs[rdn.value || ""];
  if (rdnAttr && rdnAttr[0]) {
    emit("update:modal");
    emit("ok", rdn.value + "=" + escapeRdn(rdnAttr[0]));
  }
}

// Escape an attribute value for use in an RDN (RFC 4514).
const specials = /[\\,+"<>;=]/g;
function escapeRdn(value: string): string {
  let rdn = value.replace(specials, "\\$&");
  if (rdn[0] === "#" || rdn[0] === " ") rdn = "\\" + rdn;
  if (rdn[rdn.length - 1] === " ") rdn = rdn.slice(0, -1) + "\\ ";
  return rdn;
}

function ok(key: string) {
  const rdn = props.entry.dn.split("=")[0];
  return key != rdn && !props.entry.attrs[key]!.every((val: unknown) => !val);
}
</script>
