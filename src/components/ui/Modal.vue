<template>
  <div>
    <transition name="fade">
      <div v-if="open" class="fixed w-full h-full top-0 left-0 z-20 bg-front/60 dark:bg-back/70" />
    </transition>
  
    <transition name="bounce" @enter="$emit('show')" @after-enter="$emit('shown')"
      @leave="$emit('hide')" @after-leave="$emit('hidden')">

      <div ref="backdrop" v-if="open" @click.self="onDismiss"
        class="fixed w-full h-full top-0 left-0 flex items-center justify-center z-30" >

        <div class=" absolute max-h-full w-1/2 max-w-lg container text-front overflow-hidden rounded bg-back border border-front/40">
          <div class="flex justify-between items-start">

            <div class="max-h-full w-full divide-y divide-front/30">
              <div v-if="title" class="flex justify-between items-center px-4 py-1">
                <h3 class="text-xl font-bold leading-normal">
                  <slot name="header">{{ title }}</slot>
                </h3>

                <div v-if="closable" class="control text-xl" @click="onCancel">⊗</div>
              </div>

              <div class="ui-modal-body p-4 space-y-4">
                <slot />
              </div>

              <div v-show="!hideFooter" class="flex justify-end w-full p-4 space-x-3">
                <slot name="footer">
                  <button v-if="closable" @click="onCancel" type="button" :class="'bg-' + cancelVariant">{{ cancelTitle }}</button>
                  <button @click="onOk" type="button" :class="'bg-' + okVariant">
                    <slot name="modal-ok">{{ okTitle }}</slot>
                  </button>
                </slot>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
  import { useEventListener } from '@vueuse/core';

  export default {
    name: 'Modal',

    props: {
      title: { type: String, required: true },
      open: Boolean,
      okTitle: { type: String, default: 'OK' },
      okVariant: { type: String, default: 'primary' },
      cancelTitle: { type: String, default: 'Cancel' },
      cancelVariant: { type: String, default: 'secondary' },
      closable: { type: Boolean, default: true },
      hideFooter: { type: Boolean, default: false },
    },

    methods: {
      onDismiss: function(e) {
        if (this.closable) this.onCancel(e);
      },

      onOk: function() {
        if (this.open) this.$emit('ok');
      },

      onCancel: function() {
        if (this.open) this.$emit('cancel');
      },
    },

    mounted: function() {
      if (this.closable) useEventListener(document, 'keydown', e => {
        if (e.key == 'Esc' || e.key == 'Escape') this.onDismiss();
      });
    },
  }
</script>

<style>
  .ui-modal-body label {
    @apply block text-front/70;
  }

  .ui-modal-body input, .ui-modal-body textarea, .ui-modal-body select {
    @apply w-full border border-front/20 rounded p-2 mt-1 outline-none focus:border-accent text-front bg-gray-200/80 dark:bg-gray-800/80;
  }

  .bounce-enter-active {
    animation: bounce-in 0.5s;
  }

  .bounce-leave-active {
    animation: bounce-in 0.5s reverse;
  }

  @keyframes bounce-in {
      0% { transform: scale(0); }
     50% { transform: scale(1.15); }
    100% { transform: scale(1); }
  }
</style>