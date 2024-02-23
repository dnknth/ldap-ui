<template>
  <modal title="Change / verify password" :open="modal == 'change-password'" :return-to="returnTo"
    @show="init" @shown="focus" @ok="onOk"
    @cancel="emit('update:modal')" @hidden="emit('update-form')">
    
    <div v-if="oldExists">
      <small >{{ currentUser ? 'Required' : 'Optional' }}</small>
      <i v-if="passwordOk !== undefined" class="fa ml-2"
        :class="passwordOk ? 'text-emerald-700 fa-check-circle' : 'text-danger fa-times-circle'"></i>
      
      <input ref="old" v-model="oldPassword"
        placeholder="Old password" type="password" @change="check" />
    </div>

    <input ref="changed" v-model="newPassword" placeholder="New password" type="password" />

    <input v-model="repeated" :class="{ 'text-danger': repeated && !passwordsMatch }"
      placeholder="Repeat new password" type="password" @keyup.enter="onOk" />
  </modal>
</template>

<script setup lang="ts">
  import { computed, inject, ref } from 'vue';
  import Modal from '../ui/Modal.vue';
  import type { Provided } from '../Provided';

  const props = defineProps({
      entry: { type: Object, required: true },
      modal: String,
      returnTo: String,
      user: String,
    }),

    app = inject<Provided>('app'),
    oldPassword = ref(''),
    newPassword = ref(''),
    repeated = ref(''),
    passwordOk = ref<boolean>(),

    old = ref<HTMLInputElement | null>(null),
    changed = ref<HTMLInputElement | null>(null),

    currentUser = computed(() => props.user == props.entry.meta.dn),
    passwordsMatch = computed(() => newPassword.value && newPassword.value == repeated.value),
    oldExists = computed(() => !!props.entry.attrs.userPassword
      && props.entry.attrs.userPassword[0] != ''),

    emit = defineEmits(['ok', 'update-form', 'update:modal']);

  function init() {
    oldPassword.value = newPassword.value = repeated.value = '';
    passwordOk.value = undefined;
  }

  function focus() {
    if (oldExists.value) old.value?.focus();
    else changed.value?.focus();
  }

  // Verify an existing password
  // This is optional for administrative changes
  // but required to change the current user's password
  async function check() {
    if (!oldPassword.value || oldPassword.value.length == 0) {
      passwordOk.value = undefined;
      return;
    }
    passwordOk.value = await app?.xhr({
      url: 'api/entry/password/' + props.entry.meta.dn,
      method: 'POST',
      data: JSON.stringify({ check: oldPassword.value }),
    }) as boolean;
  }

  async function onOk() {
    // old and new passwords are required for current user
    // new passwords must match
    if ((currentUser.value && !newPassword.value)
    || newPassword.value != repeated.value
    || (currentUser.value && oldExists.value && !passwordOk.value)) return;

    emit('update:modal');
    emit('ok', oldPassword.value, newPassword.value);
  }
</script>
