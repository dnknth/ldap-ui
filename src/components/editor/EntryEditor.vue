<template>
  <div v-if="entry" class="rounded border border-front/20 mb-3 mx-4 flex-auto">

    <!-- Modals for navigation menu -->
    <new-entry-dialog v-model:modal="modal" :dn="entry.meta.dn" @ok="newEntry" />
    <copy-entry-dialog v-model:modal="modal" :entry="entry" @ok="newEntry" />
    <rename-entry-dialog v-model:modal="modal" :entry="entry" @ok="renameEntry" />
    <delete-entry-dialog v-model:modal="modal" :dn="entry.meta.dn" @ok="deleteEntry" />
    <discard-entry-dialog v-model:modal="modal" :dn="activeDn" @ok="discardEntry"
      @shown="$emit('update:activeDn')" />

    <!-- Modals for main editing area -->
    <password-change-dialog v-model:modal="modal" :entry="entry" @ok="changePassword" />
    <add-photo-dialog v-model:modal="modal" attr="jpegPhoto" :dn="entry.meta.dn" @ok="load" />
    <add-photo-dialog v-model:modal="modal" attr="thumbnailPhoto" :dn="entry.meta.dn" @ok="load" />
    <add-object-class-dialog v-model:modal="modal" :entry="entry" @ok="addObjectClass" />
    
    <!-- Modals for footer -->
    <add-attribute-dialog v-model:modal="modal" :entry="entry" :attributes="may"
      @ok="addAttribute" @show-modal="modal = $event;" />
    
    <nav class="flex justify-between mb-4 border-b border-front/20">
      <div v-if="entry.meta.isNew" class="py-2 ml-3">
        <node-label :dn="entry.meta.dn" :oc="structural" />
      </div>
      <div v-else class="ml-2">
        <dropdown-menu>
          <template #button-content>
            <node-label :dn="entry.meta.dn" :oc="structural" />
          </template>
          <li @click="modal = 'new-entry';" role="menuitem">Add child…</li>
          <li @click="modal = 'copy-entry';" role="menuitem">Copy…</li>
          <li @click="modal = 'rename-entry';" role="menuitem">Rename…</li>
          <li @click="ldif" role="menuitem">Export</li>
          <li @click="modal = 'delete-entry';" class="text-danger" role="menuitem">Delete…</li>
        </dropdown-menu>
      </div>

      <div v-if="entry.meta.isNew" class="control text-2xl mr-2"
        @click="modal = 'discard-entry';">⊗</div>
      <div v-else class="control text-xl mr-2" @click="$emit('update:activeDn')">⊗</div>
    </nav>
    
    <form id="entry" class="space-y-4 my-4" @submit.prevent="save"
        @reset="load(entry.meta.dn)" @focusin="onFocus">
      <attribute-row v-for="key in keys" :key="key"
        :attr="app.schema.attr(key)" :meta="entry.meta" :values="entry.attrs[key]"
        :changed="entry.changed.includes(key)"
        :may="may.includes(key)" :must="must.includes(key)"
        @update="updateRow"
        @reload-form="load"
        @valid="valid(key, $event)"
        @show-modal="modal = $event;" />

      <!-- Footer with buttons -->
      <div class="flex ml-4 mt-2 space-x-4">
        <div class="w-1/4"></div>
        <div class="w-3/4 pl-4">
          <div class="w-[90%] space-x-3">
            <button type="submit" class="btn bg-primary"
              accesskey="s" :disabled="invalid.length != 0">Submit</button>
            <button type="reset" v-if="!entry.meta.isNew"
              class="btn bg-secondary">Reset</button>
            <button class="btn float-right bg-secondary" accesskey="a"
              v-if="!entry.meta.isNew" @click.prevent="modal = 'add-attribute';">
              Add attribute…
            </button>
          </div>
        </div>
      </div>
    </form>
  </div>
</template>

<script>
  import AddAttributeDialog from './AddAttributeDialog.vue';
  import AddObjectClassDialog from './AddObjectClassDialog.vue';
  import AddPhotoDialog from './AddPhotoDialog.vue';
  import AttributeRow from './AttributeRow.vue';
  import CopyEntryDialog from './CopyEntryDialog.vue';
  import DeleteEntryDialog from './DeleteEntryDialog.vue';
  import DiscardEntryDialog from './DiscardEntryDialog.vue';
  import DropdownMenu from '../ui/DropdownMenu.vue';
  import NewEntryDialog from './NewEntryDialog.vue';
  import NodeLabel from '../NodeLabel.vue';
  import PasswordChangeDialog from './PasswordChangeDialog.vue';
  import RenameEntryDialog from './RenameEntryDialog.vue';
  import { request } from '../../request.js';


  function unique(element, index, array) {
    return array.indexOf(element) == index;
  }

  export default {
    name: 'EntryEditor',

    components: {
      AddAttributeDialog,
      AddObjectClassDialog,
      AddPhotoDialog,
      CopyEntryDialog,
      DeleteEntryDialog,
      DiscardEntryDialog,
      DropdownMenu,
      AttributeRow,
      NewEntryDialog,
      NodeLabel,
      PasswordChangeDialog,
      RenameEntryDialog,
    },

    props: {
      activeDn: String,
    },

    inject: [ 'app' ],

    data: function() {
      return {
        entry: undefined,    // entry in editor
        focused: undefined,  // currently focused input
        invalid: [],         // field IDs with validation errors
        modal: undefined,    // pop-up dialog
      };
    },

    watch: {
      activeDn: function(dn) {
        if (!this.entry || dn != this.entry.meta.dn) this.focused = undefined;
        
        if (dn && this.entry && this.entry.meta.isNew) {
          this.modal = 'discard-entry';
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
        this.$emit('update:activeDn');
        this.prepareForm();
      },

      discardEntry: function(dn) {
        this.entry = null;
        this.$emit('update:activeDn', dn);
      },

      addAttribute: function(attr) {
        if (attr) { // FIXME: Why is this called with attr=undefined?
          this.entry.attrs[attr] = [''];
          this.prepareForm(attr + '-0');
        }
      },

      addObjectClass: function(oc) {
        if (oc) { // FIXME: Why is this called with oc=undefined?
          this.entry.attrs.objectClass.push(oc);
          const aux = this.entry.meta.aux.filter(oc => oc < oc);
          this.entry.meta.aux.splice(aux.length, 1);
          this.prepareForm();
        }
      },

      // Remove a row from the entry form
      removeObjectClass: function(newOcs) {
        const removedOc = this.entry.attrs.objectClass.filter(
            oc => !newOcs.includes(oc))[0];
        if (removedOc) {
          const aux = this.entry.meta.aux.filter(oc => oc < removedOc);
          this.entry.meta.aux.splice(aux.length, 0, removedOc);
        }
      },

      updateRow: function(attr, values, index) {
        this.entry.attrs[attr] = values;
        if (attr == 'objectClass') this.removeObjectClass(values);
        const focused = index != undefined ? attr + '-' + index : undefined;
        this.prepareForm(focused);
      },

      prepareForm: function(focused) {
        this.must.filter(attr => !this.entry.attrs[attr])
          .forEach(attr => this.entry.attrs[attr] = ['']);

        if (!focused) {
          const empty = this.keys.flatMap(attr => this.entry.attrs[attr]
            .map((value, index) => value.trim() ? undefined : attr + '-' + index)
            .filter(id => id));
          focused = empty[0];
        }

        if (!focused) focused = this.focused;

        this.$nextTick(function () {
          let input = focused ? document.getElementById(focused) : undefined;
          if (!input) input = document.querySelector('form#entry input:not([disabled])');
        
          if (input) {
            // work around annoying focus jump in OS X Safari
            window.setTimeout(() => input.focus(), 100);
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

        this.entry = await this.app.xhr({ url: 'api/entry/' + dn });
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
        const data = await this.app.xhr({
          url:  'api/entry/' + this.entry.meta.dn,
          method: this.entry.meta.isNew ? 'PUT' : 'POST',
          data: JSON.stringify(this.entry.attrs),
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });

        if (!data) return;
        
        if (data.changed && data.changed.length) {
          this.app.showInfo('👍 Saved changes');
        }
        if (this.entry.meta.isNew) {
          this.entry.meta.isNew = false;
          this.$emit('update:activeDn', this.entry.meta.dn);
        }
        else this.load(this.entry.meta.dn, data.changed);
      },

      renameEntry: async function(rdn) {
        if (rdn) { // FIXME: Why is this called with rdn=undefined?
          await this.app.xhr({
            url: 'api/rename',
            method: 'POST',
            data: JSON.stringify({
              dn:  this.entry.meta.dn,
              rdn: rdn
            }),
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
          });

          const dnparts = this.entry.meta.dn.split(',');
          dnparts.splice(0, 1, rdn);
          this.$emit('update:activeDn', dnparts.join(','));
        }
      },

      deleteEntry: async function(dn) {
        if (dn) { // FIXME: Why is this called with dn=undefined?
          if (await this.app.xhr({ url: 'api/entry/' + dn, method: 'DELETE' }) !== undefined) {
            this.app.showInfo('Deleted: ' + dn);
            this.$emit('update:activeDn', '-' + dn);
          }
        }
      },

      changePassword: async function(oldPass, newPass) {
        const data = await this.app.xhr({
          url: 'api/entry/password/' + this.entry.meta.dn,
          method: 'POST',
          data: JSON.stringify({ old: oldPass, new1: newPass }),
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });

        if (data !== undefined) {
          this.entry.attrs.userPassword = [ data ];
          this.entry.changed.push('userPassword');
        }
      },

      // Download LDIF
      ldif: async function() {
        const data = await request({
          url: 'api/ldif/' + this.entry.meta.dn,
          responseType: 'blob' });
        if (!data) return;

        const a = document.createElement("a"),
            url = URL.createObjectURL(data.response);
        a.href = url;
        a.download = this.entry.meta.dn.split(',')[0].split('=')[1] + '.ldif';
        document.body.appendChild(a);
        a.click();
      },
      
      attributes: function(kind) {
        let attrs = this.entry.attrs.objectClass
          .filter(oc => oc && oc != 'top')
          .map(oc => this.app.schema.oc(oc))
          .flatMap(oc => oc ? oc.$collect(kind): [])
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
          .map(oc => this.app.schema.oc(oc))
          .filter(oc => oc && oc.structural)[0];
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
