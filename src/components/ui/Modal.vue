<template>
  <div>
    <transition name="fade">
      <div v-if="open" class="fixed w-full h-full top-0 left-0 z-20 bg-front/60 dark:bg-back/70" />
    </transition>
  
    <transition name="bounce" @enter="emit('show')" @after-enter="emit('shown')"
      @leave="emit('hide')" @after-leave="emit('hidden')">

      <div ref="backdrop" v-if="open" @click.self="onCancel" @keydown.esc="onCancel"
        class="fixed w-full h-full top-0 left-0 flex items-center justify-center z-30" >

        <div class="absolute max-h-full w-1/2 max-w-lg container text-front overflow-hidden rounded bg-back border border-front/40">
          <div class="flex justify-between items-start">

            <div class="max-h-full w-full divide-y divide-front/30">
              <div v-if="title" class="flex justify-between items-center px-4 py-1">
                <h3 class="ui-modal-header text-xl font-bold leading-normal">
                  <slot name="header">{{ title }}</slot>
                </h3>

                <div class="control text-xl" @click="onCancel" title="close">⊗</div>
              </div>

              <div class="ui-modal-body p-4 space-y-4">
                <slot />
              </div>

              <div v-show="!hideFooter" class="ui-modal-footer flex justify-end w-full p-4 space-x-3">
                <slot name="footer">
                  <button id="ui-modal-cancel" @click="onCancel" type="button" :class="cancelClasses">
                    <slot name="modal-cancel">{{ cancelTitle }}</slot>
                  </button>
                  <button id="ui-modal-ok" @click.stop="onOk" type="button" :class="okClasses">
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

<script setup>
  const props = defineProps({
      title: { type: String, required: true },
      open: { type: Boolean, required: true },
      okTitle: { type: String, default: 'OK' },
      okClasses: { type: String, default: 'bg-primary/80' },
      cancelTitle: { type: String, default: 'Cancel' },
      cancelClasses: { type: String, default: 'bg-secondary' },
      hideFooter: { type: Boolean, default: false },
      returnTo: String,
    }),
    emit = defineEmits(['ok', 'cancel', 'show', 'shown', 'hide', 'hidden']);

  function onOk() {
    if (props.open) emit('ok');
  }

  function onCancel() {
    if (props.open) {
      if (props.returnTo) document.getElementById(props.returnTo).focus();
      emit('cancel');
    }
  }
</script>

<style>
  .ui-modal-body label {
    @apply block text-front/70;
  }

  .ui-modal-body input, .ui-modal-body textarea, .ui-modal-body select {
    @apply w-full border border-front/20 rounded p-2 mt-1 outline-none focus:border-primary text-front bg-gray-200/80 dark:bg-gray-800/80;
  }

  .ui-modal-footer button {
    min-width: 5rem;
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