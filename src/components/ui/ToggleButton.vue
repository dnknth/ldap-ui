<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ value?: string }>(),
  emit = defineEmits<{ "update:value": [value: string] }>(),
  on = computed(() => props.value == "TRUE");
</script>

<template>
  <button type="button" class="p-0 relative focus:outline-none" tabindex="0"
    @click="emit('update:value', !on ? 'TRUE' : 'FALSE')">
    <div class="w-8 h-4 transition rounded-full bg-gray-200"></div>
    <div
      class="absolute top-0 left-0 w-4 h-4 transition-all duration-200 ease-in-out transform scale-110 rounded-full shadow-sm"
      :class="on ? 'translate-x-4 bg-primary' : 'translate-x-0 bg-secondary'"></div>
  </button>
</template>
