<template>
  <modal
    title="Log in"
    :open="true"
    :dismissible="false"
    :close-on-backdrop="false"
    @shown="shown"
    @ok="onOk"
  >
    <small>{{ hint }}</small>

    <input
      ref="username"
      v-model="username"
      placeholder="Username"
      type="text"
      autocomplete="username"
      autofocus
      @keyup.enter="onOk"
    />

    <input
      ref="password"
      v-model="password"
      placeholder="Password"
      type="password"
      autocomplete="new-password"
      @keyup.enter="onOk"
    />

    <small v-if="error" class="text-danger">{{ error }}</small>
  </modal>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, useTemplateRef } from "vue";
import Modal from "./ui/Modal.vue";
import { getWhoAmI } from "@/generated";
import { setPendingCredentials, clearPendingCredentials } from "@/auth";

const username = ref(""),
  password = ref(""),
  error = ref(""),
  usernameInput = useTemplateRef("username"),
  passwordInput = useTemplateRef("password"),
  emit = defineEmits<{
    ok: [username: string, password: string, userDn: string];
  }>();

const hint = "Authenticate against the LDAP directory.";

// Force the fields empty on mount: browser password managers autofill
// type="password" inputs on load, and the autofilled value would otherwise
// appear already-entered (and, in some browsers, non-editable).
function resetFields() {
  username.value = "";
  password.value = "";
  passwordInput.value?.setAttribute("autocomplete", "new-password");
}

function focus() {
  usernameInput.value?.focus();
}

// The dialog is re-created from scratch on each logout (v-if in App.vue), so
// focus must be applied on mount: the HTML `autofocus` attribute is not
// reliably honored for dynamically re-inserted elements, and the modal's
// bounce transition reports "shown" only after its animation.
onMounted(async () => {
  resetFields();
  await nextTick();
  focus();
});

function shown() {
  resetFields();
  focus();
}

async function onOk() {
  // Read from the DOM: browser autofill sets input.value directly without an
  // `input` event, so v-model's refs can be empty even though the fields show
  // text. Falling back to the refs covers keyboard input, which does fire it.
  const name = usernameInput.value?.value || username.value;
  const pass = passwordInput.value?.value || password.value;
  if (!name || !pass) return;

  // Authenticate the verification request without committing the global
  // credentials (which would unmount this dialog before we emit). whoami is a
  // lightweight endpoint that returns the bound user's DN on success and an
  // empty string for invalid credentials — cheaper than fetching the whole
  // schema just to validate.
  setPendingCredentials(name, pass);
  error.value = "";

  const response = await getWhoAmI();
  // whoami is soft: bad credentials get 200 + an empty DN, never a 401. A
  // non-200 (or a failed request) means the directory cannot be reached /
  // configured — that is not the user's credentials, so say so.
  const status = response.response?.status;
  if (status && status !== 200) {
    clearPendingCredentials();
    error.value =
      "Cannot reach the LDAP directory. Check the connection and configuration.";
    return;
  }
  if (response.error || !response.data) {
    clearPendingCredentials();
    error.value = "Invalid credentials. Please try again.";
    return;
  }

  clearPendingCredentials();
  emit("ok", name, pass, response.data);
}
</script>
