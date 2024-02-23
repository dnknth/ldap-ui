<template>
  <div class="max-w-sm rounded overflow-hidden shadow-lg border border-front/20">
    <slot name="header">
      <div class="py-2 border-b border-front/20">
        <strong class="pl-6">{{ title }}</strong>
        <span class="control text-l float-right mr-2 pl-2" title="close"
          @click="emit('close')">⊗
        </span>
      </div>
    </slot>
    <div class="px-6 py-2">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
  defineProps({
    title: { type: String, required: true },
  });

  const emit = defineEmits(['close']);
</script>