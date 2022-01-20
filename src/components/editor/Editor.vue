<template>
  <!-- Entry editor form -->
  <b-form v-if="entry" id="entry-form"
    @submit.prevent="save" @reset="loadEntry(entry.meta.dn);"
    @focusin="onFocus" @click="onFocus">

    <new-entry-dialog :entry="entry" @select-dn="$emit('select-dn')"
      @replace-entry="replaceEntry" @update-form="prepareForm" />
    <copy-entry-dialog v-model="entry"
      @select-dn="$emit('select-dn', $event)" @update-form="prepareForm" />
    <rename-entry-dialog :dn="entry.meta.dn" :entry="entry" :info="showInfo"
      @select-dn="$emit('select-dn', $event)" />
    <delete-entry-dialog :dn="entry.meta.dn" :info="showInfo"
      @select-dn="$emit('select-dn', $event)" />
    <discard-entry-dialog v-model="entry" :dn="activeDn"
      @select-dn="$emit('select-dn', $event)" />

    <password-change-dialog v-model="entry" :info="showInfo" />
    <add-photo-dialog :dn="entry.meta.dn" @select-dn="loadEntry" />
    <add-attribute-dialog v-model="entry" :attributes="optional"
      @update-form="prepareForm" />
    <add-object-class-dialog :entry="entry"
      @replace-entry="replaceEntry" @update-form="prepareForm" />
  
    <b-card id="editor">
      <div class="header" slot="header">
        <b-nav>
          <b-nav-item v-if="entry.meta.isNew">
            <node-label :dn="entry.meta.dn" :oc="structural" />
          </b-nav-item>
          <b-nav-item-dropdown v-else extra-toggle-classes="nav-link-custom" right class="entry-menu">
            <template #button-content>
              <node-label :dn="entry.meta.dn" :oc="structural" />
            </template>
            <b-dropdown-item v-b-modal.new-entry>Add child…</b-dropdown-item>
            <b-dropdown-item v-b-modal.copy-entry>Copy…</b-dropdown-item>
            <b-dropdown-item v-b-modal.rename-entry>Rename…</b-dropdown-item>
            <b-dropdown-item @click="ldif">Export</b-dropdown-item>
            <b-dropdown-item v-b-modal.confirm><span class="red">Delete…</span></b-dropdown-item>
          </b-nav-item-dropdown>
        </b-nav>
        <span v-if="entry.meta.isNew" class="control close-box" v-b-modal.confirm-discard>⊗</span>
        <span v-else class="control close-box" @click="$emit('select-dn')">⊗</span>
      </div>
      
      <table id="entry">
        <form-row v-for="key in keys" class="attr" :key="key" :required="required.includes(key)"
          :attr="schema.attr(key)" :meta="entry.meta" :marked="marked" v-model="entry.attrs[key]"
          :changed="entry.changed.includes(key)" :structural="schema.structural"
          @form-changed="prepareForm" @reload-form="loadEntry"
          @display-oc="$emit('display-oc', $event)" @display-attr="$emit('display-attr', $event)" />

        <tr>
          <th></th>
          <td>
            <div class="button-bar">
              <b-button type="submit" variant="primary" accesskey="s">Submit</b-button>
              <b-button type="reset" v-if="!entry.meta.isNew">Reset</b-button>
              <b-button class="right" v-if="!entry.meta.isNew" v-b-modal.add-attribute accesskey="a">
                Add attribute…
              </b-button>
            </div>
          </td>
        </tr>
      </table>      
    </b-card>
  </b-form>
</template>

<script>

import AddAttributeDialog from './AddAttributeDialog.vue'
import AddObjectClassDialog from './AddObjectClassDialog.vue'
import AddPhotoDialog from './AddPhotoDialog.vue'
import CopyEntryDialog from './CopyEntryDialog.vue'
import DeleteEntryDialog from './DeleteEntryDialog.vue'
import DiscardEntryDialog from './DiscardEntryDialog.vue'
import FormRow from './FormRow.vue'
import NewEntryDialog from './NewEntryDialog.vue'
import NodeLabel from '../NodeLabel.vue'
import PasswordChangeDialog from './PasswordChangeDialog.vue'
import RenameEntryDialog from './RenameEntryDialog.vue'

export default {

  name: 'Editor',

  components: {
    AddAttributeDialog,
    AddObjectClassDialog,
    AddPhotoDialog,
    CopyEntryDialog,
    DeleteEntryDialog,
    DiscardEntryDialog,
    FormRow,
    NewEntryDialog,
    NodeLabel,
    PasswordChangeDialog,
    RenameEntryDialog,
  },

  props: {
    activeDn: String,
    showInfo: {
      type: Function,
      required: true,
    },
  },

  model: {
    prop: 'activeDn',
    event: 'select-dn'
  },

  inject: [ 'xhr', 'getSchema' ],

  data: function() {
    return {
      entry: null,    // entry in editor
      focused: null,  // currently focused input
      marked: false,
    }
  },

  watch: {
    activeDn: function(dn) {
      if (!this.entry || dn != this.entry.meta.dn) this.focused = undefined;
      
      if (dn && this.entry && this.entry.meta.isNew) {
        this.$bvModal.show('confirm-discard');
      }
      else if (dn) this.loadEntry(dn);
      else if (this.entry && !this.entry.meta.isNew) this.entry = null;
    }
  },

  methods: {

    // Clean up UI state on focus changes and clicks
    onFocus: function(evt) {
      const el = evt.target;
      if (el.tagName == 'INPUT' && el.id && el.form.id == 'entry-form')  {
        this.focused = el.id;
      }
    },

    replaceEntry: function(entry) {
      this.entry = Object.assign({}, entry);
      const attrs = Object.keys(this.entry.attrs);
      this.entry.meta.required = this.required;
      this.required.filter(attr => !attrs.includes(attr))
        .forEach(attr => { entry.attrs[attr] = ['']; });
    },

    prepareForm: function(focused) {
      this.entry = Object.assign({}, this.entry); // redraw

      if (!focused) {
        const attrs = this.entry.attrs,
          empty = this.keys.filter(attr => attrs[attr][0] == '');
        if (empty[0]) focused = empty[0] + '-0';
      }

      this.$nextTick(function () {
        document.querySelectorAll('input').forEach(function(el) {
          el.removeAttribute('disabled');
        });
        document.querySelectorAll('input.disabled').forEach(function(el) {
          el.setAttribute('disabled', 'disabled');
        });
        let input = focused ? document.getElementById(focused) : undefined;
        if (!input) input = document.querySelector('#entry input:not([disabled])');
        if (input) input.focus();
      });
    },

    // Load an entry into the editing form
    loadEntry: async function(dn, changed, focused) {

      if (!dn || dn.startsWith('-')) {
        this.entry = null;
        return;
      }

      this.entry = await this.xhr({ url: 'api/entry/' + dn });
      if (!this.entry) return;

      this.entry.changed = changed || [];
      this.entry.meta.isNew = this.marked = false;

      document.title = dn.split(',')[0];
      this.prepareForm(focused || this.focused);
    },

    // Download LDIF
    ldif: async function() {
      const xhr = await this.xhr({
        url: 'api/ldif/' + this.entry.meta.dn,
        responseType: 'blob'
      });
      if (!xhr) return;

      var a = document.createElement("a"),
          url = URL.createObjectURL(xhr.response);
      a.href = url;
      a.download = this.entry.meta.dn.split(',')[0].split('=')[1] + '.ldif';
      document.body.appendChild(a);
      a.click();
    },
    
    // Submit the entry form via AJAX
    save: async function() {
      this.marked = this.invalid;
      if (this.marked) {
        this.prepareForm();
        return;
      }

      this.entry.changed = [];
      const data = await this.xhr({
        url:  'api/entry/' + this.entry.meta.dn,
        method: this.entry.meta.isNew ? 'PUT' : 'POST',
        data: JSON.stringify(this.entry.attrs),
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
      });

      if (!data) return;
      
      if (data.changed && data.changed.length) {
        this.showInfo('👍 Saved changes');
      }
      if (this.entry.meta.isNew) {
        this.entry.meta.isNew = false;
        this.$emit('select-dn', this.entry.meta.dn);
      }
      else this.loadEntry(this.entry.meta.dn, data.changed, this.focused);
    },

    attributes: function(kind) {
      const schema = this.schema,
        required = this.entry.attrs['objectClass']
          .filter(oc => oc && oc != 'top')
          .flatMap(oc => schema.oc(oc).getAttributes(kind))
          .filter((element, index, array) => array.indexOf(element) == index); // uniqueness
      required.sort();
      return required;
    },


  },

  computed: {

    schema: function() { return this.getSchema(); },

    keys: function() {
      let keys = Object.keys(this.entry.attrs);
      keys.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
      return keys;
    },

    structural: function() {
      return this.entry.attrs['objectClass'].filter(
        oc => this.schema.oc(oc).isStructural)[0];
    },

    required: function() {
      return this.attributes('must');
    },

    optional: function() {
      return this.attributes('may');
    },

    invalid: function() {
      const attrs = this.entry.attrs;
      return this.required
        .some(key => attrs[key].every(val => !val));
    },
  },
}
</script>

<style>
  #editor {
    max-width: 1024px;
  }

  #editor div.card-header {
    padding: 0.45ex 0;
  }

  table#entry {
    width: 100%;
  }

  table#entry div.button-bar {
    width: 90%;
  }

  li.entry-menu a.nav-link {
    padding-left: 8px;
  }

  div.button-bar button[type='submit'] {
    margin-right: 0.5em;
  }

  th {
    font-weight: normal;
  }
</style>
