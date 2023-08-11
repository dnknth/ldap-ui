<template>
  <transition name="fade" @after-enter="$emit('opened')" @after-leave="$emit('closed')">
    <div v-if="open" 
      class="ui-popover absolute z-10 border border-front/70 rounded min-w-max text-front bg-back list-none">
      <ul class="bg-front/5 dark:bg-front/10 py-2" @click="close">
        <slot></slot>
      </ul>
    </div>
  </transition>
</template>

<script>
  import { useEventListener } from '@vueuse/core';

  export default {
    name: 'Popover',

    props: {
      open: Boolean,
    },

    methods: {
      close: function() {
        if (this.open) {
          this.$emit('update:open');
        }
      },
    },

    mounted: function() {
      useEventListener(document, 'keydown', e => {
        if (e.key == 'Esc' || e.key == 'Escape') this.close();
      });
      useEventListener(document, 'click', this.close);
    },
  }
</script>

<style>
  .ui-popover [role=menuitem] {
    @apply cursor-pointer px-4 hover:bg-front/70 hover:text-back;
  }
</style>