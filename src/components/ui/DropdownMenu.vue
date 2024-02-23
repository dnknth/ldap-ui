<template>
  <div class="relative inline-block text-left mx-1">
    <span ref="opener" class="inline-flex w-full py-2 select-none cursor-pointer"
      :aria-expanded="open" aria-haspopup="true" @click.stop="open = !open">
      <slot name="button-content">
        {{ title }}
      </slot>
      <svg class="-mr-1 h-5 w-5 pt-1" viewBox="0 0 20 20" fill="currentColor" :aria-hidden="!open">
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
      </svg>
    </span>
    <popover v-model:open="open">
      <slot></slot>
    </popover>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import Popover from './Popover.vue';

  const open = ref(false);
  defineProps({ title: String });
</script>
