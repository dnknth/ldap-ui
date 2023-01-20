<template>
  <!-- Entry editor form -->
  <b-form v-if="entry" id="entry-form"
    @submit.prevent="save" @reset="load(entry.meta.dn);" @focusin="onFocus">

    <new-entry-dialog :entry="entry" :schema="schema"
      @replace-entry="newEntry"
      @select-dn="$emit('select-dn')" />
    <copy-entry-dialog :entry="entry"
      @select-dn="$emit('select-dn', $event)" />
    <rename-entry-dialog :dn="entry.meta.dn" :entry="entry"
      @select-dn="$emit('select-dn', $event)" />
    <delete-entry-dialog :dn="entry.meta.dn" :info="showInfo"
      @select-dn="$emit('select-dn', $event)" />
    <discard-entry-dialog :dn="activeDn"
      @replace-entry="entry = $event;"
      @select-dn="$emit('select-dn', $event)" />

    <password-change-dialog :entry="entry" :user="user" />
    <add-photo-dialog id="upload-jpegPhoto" attr="jpegPhoto" :dn="entry.meta.dn" @select-dn="load" />
    <add-photo-dialog id="upload-thumbnailPhoto" attr="thumbnailPhoto" :dn="entry.meta.dn" @select-dn="load" />
    <add-attribute-dialog :entry="entry" :attributes="may" @update-form="prepareForm" />
    <add-object-class-dialog :entry="entry" @update-form="prepareForm" />
  
    <b-card id="editor">
      <div>
        <slot name="header">
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
          <span v-if="entry.meta.isNew" class="close-box control" v-b-modal.confirm-discard>⊗</span>
          <span v-else class="close-box control" @click="$emit('select-dn')">⊗</span>
        </slot>
      </div>
      
      <table id="entry">
        <form-row v-for="key in keys" class="attr" :key="key" :must="must.includes(key)"
          :attr="schema.attr(key)" :meta="entry.meta" :values="entry.attrs[key]"
          :changed="entry.changed.includes(key)" :structural="schema.structural" :base-dn="baseDn"
          :may="may.includes(key)" @form-changed="prepareForm"
          @reload-form="load" @valid="valid(key, $event)"
          @display-oc="$emit('display-oc', $event)" @display-attr="$emit('display-attr', $event)" />

        <tr>
          <th></th>
          <td>
            <div class="button-bar">
              <b-button type="submit" variant="primary" accesskey="s" :disabled="invalid.length != 0">Submit</b-button>
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

import AddAttributeDialog from './AddAttributeDialog.vue';
import AddObjectClassDialog from './AddObjectClassDialog.vue';
import AddPhotoDialog from './AddPhotoDialog.vue';
import CopyEntryDialog from './CopyEntryDialog.vue';
import DeleteEntryDialog from './DeleteEntryDialog.vue';
import DiscardEntryDialog from './DiscardEntryDialog.vue';
import FormRow from './FormRow.vue';
import NewEntryDialog from './NewEntryDialog.vue';
import NodeLabel from '../NodeLabel.vue';
import PasswordChangeDialog from './PasswordChangeDialog.vue';
import RenameEntryDialog from './RenameEntryDialog.vue';
import { request } from '../../request.js';


function unique(element, index, array) {
  return array.indexOf(element) == index;
}


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
    baseDn: String,
    user: String,

    showInfo: {
      type: Function,
      required: true,
    },

    schema: {
      type: Object,
      required: true,
    },
  },

  model: {
    prop: 'activeDn',
    event: 'select-dn'
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      entry: null,    // entry in editor
      focused: null,  // currently focused input
      invalid: [],
    }
  },

  watch: {
    activeDn: function(dn) {
      if (!this.entry || dn != this.entry.meta.dn) this.focused = undefined;
      
      if (dn && this.entry && this.entry.meta.isNew) {
        this.$bvModal.show('confirm-discard');
      }
      else if (dn) this.load(dn);
      else if (this.entry && !this.entry.meta.isNew) this.entry = null;
    }
  },

  methods: {

    // Track focus changes
    onFocus: function(evt) {
      const el = evt.target;
      if (el.tagName == 'INPUT' && el.id) this.focused = el.id;
    },

    newEntry: function(entry) {
      this.entry = entry;
      this.prepareForm();
    },

    prepareForm: function(focused) {
      this.must.filter(attr => !this.entry.attrs[attr])
        .forEach(attr => this.$set(this.entry.attrs, attr, ['']));

      if (!focused) {
        const empty = this.keys.flatMap(attr => this.entry.attrs[attr]
          .map((value, index) => value.trim() ? undefined : attr + '-' + index)
          .filter(id => id));
        focused = empty[0];
      }

      if (!focused) focused = this.focused;

      this.$nextTick(function () {
        let input = focused ? document.getElementById(focused) : undefined;
        if (!input) input = document.querySelector('#entry input:not([disabled])');
      
        if (input) {
          // work around annoying focus jump in OS X Safari
          window.setTimeout(function() { input.focus(); }, 100);
          this.focused = input.id;
        }
      });
    },

    // Load an entry into the editing form
    load: async function(dn, changed) {
      this.invalid = [];

      if (!dn || dn.startsWith('-')) {
        this.entry = null;
        return;
      }

      this.entry = await this.xhr({ url: 'api/entry/' + dn });
      if (!this.entry) return;

      this.entry.changed = changed || [];
      this.entry.meta.isNew = false;

      document.title = dn.split(',')[0];
      this.prepareForm();
    },

    // Submit the entry form via AJAX
    save: async function() {
      if (this.invalid.length > 0) {
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
      else this.load(this.entry.meta.dn, data.changed);
    },

    // Download LDIF
    ldif: async function() {
      const xhr = await request({
        url: 'api/ldif/' + this.entry.meta.dn,
        responseType: 'blob'
      }).catch(xhr => console.error(xhr));
      if (!xhr) return;

      const a = document.createElement("a"),
          url = URL.createObjectURL(xhr.response);
      a.href = url;
      a.download = this.entry.meta.dn.split(',')[0].split('=')[1] + '.ldif';
      document.body.appendChild(a);
      a.click();
    },
    
    attributes: function(kind) {
      let attrs = this.entry.attrs.objectClass
        .filter(oc => oc && oc != 'top')
        .map(oc => this.schema.oc(oc))
        .flatMap(oc => oc ? oc.getAttributes(kind): [])
        .filter(unique);
      attrs.sort();
      return attrs;
    },

    valid: function(key, valid) {
      if (valid) {
        const pos = this.invalid.indexOf(key);
        if (pos >= 0) this.invalid.splice(pos, 1);
      }
      else if (!valid && !this.invalid.includes(key)) {
        this.invalid.push(key);
      }
    },

},

  computed: {

    keys: function() {
      let keys = Object.keys(this.entry.attrs);
      keys.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
      return keys;
    },

    structural: function() {
      const oc = this.entry.attrs.objectClass
        .map(oc => this.schema.oc(oc))
        .filter(oc => oc && oc.isStructural)[0];
      return oc ? oc.name : '';
    },

    must: function() {
      return this.attributes('must');
    },

    may: function() {
      return this.attributes('may');
    },
},
}
</script>

<style scoped>
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
</style>
