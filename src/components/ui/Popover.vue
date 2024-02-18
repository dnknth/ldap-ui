<template>
  <transition name="fade" @after-enter="emit('opened')" @after-leave="emit('closed')">
    <div v-if="open" 
      class="ui-popover absolute z-10 border border-front/70 rounded min-w-max text-front bg-back list-none">
      <ul class="bg-front/5 dark:bg-front/10 py-2" ref="items" @click="close">
        <slot></slot>
      </ul>
    </div>
  </transition>
</template>

<script setup>
  import { onMounted, ref, watch } from 'vue';
  import { useEventListener, useMouseInElement } from '@vueuse/core';

  const props = defineProps({ open: Boolean }),
    emit = defineEmits(['opened', 'closed', 'update:open', 'select']),
    items = ref(null),
    selected = ref(null),
    { isOutside } = useMouseInElement(items);

  function close() {
    selected.value = undefined;
    if (props.open) emit('update:open');
  }

  function move(offset) {
    const maxpos = items.value.children.length - 1;
    if (selected.value == null) {
      selected.value = offset > 0 ? 0 : maxpos;
    }
    else {
      selected.value += offset;
      if (selected.value > maxpos) selected.value = 0;
      else if (selected.value < 0) selected.value = maxpos;
    }
  }

  function scroll(e) {
    if (!props.open || !items.value) return;
    switch (e.key) {
      case 'Esc':
      case 'Escape':
        close();
        break;
      case 'ArrowDown':
        move(1);
        e.preventDefault();
        break;
      case 'ArrowUp':
        move(-1);
        e.preventDefault();
        break;
      case 'Enter':
        emit('select', selected.value);
        e.preventDefault();
        break;
    }
  }

  onMounted(() => {
    useEventListener(document, 'keydown', scroll);
    useEventListener(document, 'click', close);
  });

  watch(selected, (pos) => {
    if (!props.open || !items.value) return;
    for (let child of items.value.children) {
      child.classList.remove('selected');
    }
    if (pos != null) items.value.children[pos].classList.add('selected');
  });

  watch(isOutside, (outside) => {
    for (let child of items.value.children) {
      if (outside) {
        child.classList.remove('hover:bg-primary/40');
      }
      else {
        selected.value = null;
        child.classList.add('hover:bg-primary/40');
      }
    }
  });
</script>

<style>
  .ui-popover [role=menuitem] {
    @apply cursor-pointer px-4;
  }
  .ui-popover [role=menuitem].selected {
    @apply bg-primary/40;
  }
</style>