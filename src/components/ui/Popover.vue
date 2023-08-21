<template>
  <transition name="fade" @after-enter="emit('opened')" @after-leave="emit('closed')">
    <div v-if="open" 
      class="ui-popover absolute z-10 border border-front/70 rounded min-w-max text-front bg-back list-none">
      <ul class="bg-front/5 dark:bg-front/10 py-2" @click="close">
        <slot></slot>
      </ul>
    </div>
  </transition>
</template>

<script setup>
  import { onMounted } from 'vue';
  import { useEventListener } from '@vueuse/core';

  const props = defineProps({ open: Boolean }),
    emit = defineEmits(['opened', 'closed', 'update:open']);

  function close() {
    if (props.open) emit('update:open');
  }

  onMounted(() => {
    useEventListener(document, 'keydown', e => {
      if (e.key == 'Esc' || e.key == 'Escape') close();
    });
    useEventListener(document, 'click', close);
  });
</script>

<style>
  .ui-popover [role=menuitem] {
    @apply cursor-pointer px-4 hover:bg-primary/40;
  }
</style>