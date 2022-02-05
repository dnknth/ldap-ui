<template>
  <b-modal id="change-password" title="Change / verify password"
    @show="reset" @shown="init" @ok="done" @hidden="$emit('update-form')">
    
    <div v-if="oldExists">
      <small >{{ currentUser ? 'Required' : 'Optional' }}</small>
      <i v-if="passwordOk !== undefined" class="fa"
        :class="passwordOk ? 'green fa-check-circle' : 'red fa-times-circle'"></i>
      
      <input id="old-password" v-model="oldPassword" class="mb-3 form-control"
        placeholder="Old password" type="password" @change="check" />
    </div>

    <input id="new-password" v-model="newPassword" class="mb-3 form-control"
      placeholder="New password" type="password" />

    <input v-model="repeated" class="mb-3 form-control"
      :class="{ red: repeated &amp;&amp; !passwordsMatch }"
      placeholder="Repeat new password" type="password" @keyup.enter="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'PasswordChangeDialog',

  props: {
    entry: {
      type: Object,
      required: true
    },

    user: {
      type: String,
      required: true,
    },
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

    reset: function() {
      this.oldPassword = this.newPassword = this.repeated = '';
      this.passwordOk = undefined;
    },

    init: function() {
      document.getElementById(this.oldExists ? 'old-password' : 'new-password').focus();
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

    done: async function(evt) {
      // old and new passwords are required for current user
      // new passwords must match
      if ((this.currentUser && !this.newPassword)
      || this.newPassword != this.repeated
      || (this.currentUser && this.oldExists && !this.passwordOk)) {
        evt.preventDefault();
        return;
      }
      
      const data = await this.xhr({
          url: 'api/entry/password/' + this.entry.meta.dn,
          method: 'POST',
          data: JSON.stringify({ old: this.oldPassword, new1: this.newPassword }),
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });

      if (data !== undefined) {
        this.$set(this.entry.attrs, 'userPassword', [ data ]);
        this.entry.changed.push('userPassword');
        this.$bvModal.hide('change-password');
      }
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

<style scoped>
  #change-password input {
    display: inline;
  }

  #change-password i {
    margin-left: 0.5em;
  }

  .red {
    color: red !important;
  }
</style>
