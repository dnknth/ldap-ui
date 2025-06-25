<template>
  <span @click="onClick(dn)" :title="dn" class="node-label cursor-pointer select-none">
    <i class="fa w-6 text-center" :class="icon" v-if="oc"></i>
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";
const props = defineProps<{
  dn: string;
  oc?: string;
}>(),
  icons: { [key: string]: string } = {
    // OC -> icon mapping
    account: "user",
    groupOfNames: "users",
    groupOfURLs: "users",
    groupOfUniqueNames: "users",
    inetOrgPerson: "address-book",
    krbContainer: "lock",
    krbPrincipal: "user-o",
    krbRealmContainer: "globe",
    organization: "globe",
    organizationalRole: "android",
    organizationalUnit: "sitemap",
    person: "user",
    posixGroup: "users",
  },
  icon = computed(() =>
    // Get the icon for an OC
    props.oc ? " fa-" + (icons[props.oc] || "question") : "fa-question",
  ),
  // Shorten a DN for readability
  label = computed(() =>
    (props.dn || "")
      .split(",")[0]
      .replace(/^cn=/, "")
      .replace(/^krbPrincipalName=/, ""),
  ),
  emit = defineEmits<{ "select-dn": [dn: string] }>();

function onClick(dn: string) {
  if (dn) emit("select-dn", dn);
}
</script>
