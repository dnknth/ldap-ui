<template>
  <modal title="Change / verify password" :open="modal == 'change-password'"
    @show="init" @shown="focus" @ok="onOk"
    @cancel="$emit('close')" @hidden="$emit('update-form')">
    
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

<script>
  import Modal from '../Modal.vue';

  export default {
    name: 'PasswordChangeDialog',

    components: {
      Modal,
    },

    props: {
      entry: Object,
      user: String,
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    inject: [ 'xhr' ],

    data: function() {
      return {
        oldPassword: '',
        newPassword: '',
        repeated: '',
        passwordOk: undefined,
      }
    },

    methods: {
      init: function() {
        this.oldPassword = this.newPassword = this.repeated = '';
        this.passwordOk = undefined;
      },

      focus: function() {
        if (this.oldExists) this.$refs.old.focus();
        else this.$refs.changed.focus();
      },

      // Verify an existing password
      // This is optional for administrative changes
      // but required to change the current user's password
      check: async function() {
        if (!this.oldPassword || this.oldPassword.length == 0) {
          this.passwordOk = undefined;
          return;
        }
        this.passwordOk = await this.xhr({
          url: 'api/entry/password/' + this.entry.meta.dn,
          method: 'POST',
          data: JSON.stringify({ check: this.oldPassword }),
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });
      },

      onOk: async function() {
        // old and new passwords are required for current user
        // new passwords must match
        if ((this.currentUser && !this.newPassword)
        || this.newPassword != this.repeated
        || (this.currentUser && this.oldExists && !this.passwordOk)) return;

        this.$emit('close');
        this.$emit('ok', this.oldPassword, this.newPassword);
      },
    },

    computed: {
      currentUser: function() {
        return this.user == this.entry.meta.dn;
      },

      // Verify that the new password is repeated correctly
      passwordsMatch: function() {
        return this.newPassword && this.newPassword == this.repeated;
      },

      oldExists: function() {
        return this.entry.attrs.userPassword
        && this.entry.attrs.userPassword[0] != '';
      },
    }
  }
</script>
