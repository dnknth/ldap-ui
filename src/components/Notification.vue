<template>
  <transition name="fade">
    <div v-if="alert" :class="alert.color"
    class="rounded mx-4 mb-4 p-3 border border-front/70 text-front/70 dark:text-back/70">
      {{ alert.msg }}
    <span class="float-right control" @click="emit('update:alert')">✖</span>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { watch } from "vue";
import type { Alert } from "./Alert";

const
  props = defineProps<{
    alert?: Alert;
  }>(),
  emit = defineEmits<{
    "update:alert": [error?: Alert];
  }>();

watch(() => props.alert, (e) => {
  if (e) setTimeout(() => { emit("update:alert"); }, e.timeout * 1000);
});
</script>
