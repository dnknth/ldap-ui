<template>
  <div :class="{ hidden : !open }" v-on-click-outside="close"
    class="absolute z-10 border border-front/70 rounded min-w-max text-front bg-back list-none">
    <ul class="bg-front/5 dark:bg-front/10 py-2" @click="close">
      <slot></slot>
    </ul>
  </div>
</template>

<script>
  import { useEventListener } from '@vueuse/core';
  import { vOnClickOutside } from '@vueuse/components';

  export default {
    name: 'Popover',

    props: {
      open: Boolean,
    },

    directives: {
      'on-click-outside': vOnClickOutside,
    },

    methods: {
      close: function(evt) {
        if (this.open) {
          evt.stopPropagation();
          this.$emit('close');
        }
      },
    },

    mounted: function() {
      useEventListener(document, "keydown", e => {
        if (e.key == "Esc" || e.key == "Escape") this.close(e);
      });

    },
  }
</script>

<style scoped>
  [role=menuitem] {
    @apply cursor-pointer px-4 hover:bg-front/70 hover:text-back;
  }
</style>
