<template>
  <div v-if="entry" class="rounded border border-front/20 mb-3 mx-4 flex-auto">

    <!-- Modals for navigation menu -->
    <new-entry-dialog v-model="modal" :entry="entry" :schema="schema" @ok="newEntry" />
    <copy-entry-dialog v-model="modal" :entry="entry" @ok="newEntry" />
    <rename-entry-dialog v-model="modal" :entry="entry" @ok="renameEntry" />
    <delete-entry-dialog v-model="modal" :dn="entry.meta.dn" @ok="deleteEntry" />
    <discard-entry-dialog v-model="modal" :dn="activeDn" @ok="discardEntry"
      @shown="$emit('select-dn')" />

    <!-- Modals for main editing area -->
    <password-change-dialog v-model="modal" :entry="entry" :user="user"
      @ok="changePassword" />
    <add-photo-dialog v-model="modal" attr="jpegPhoto" :dn="entry.meta.dn" @ok="load" />
    <add-photo-dialog v-model="modal" attr="thumbnailPhoto" :dn="entry.meta.dn" @ok="load" />
    <add-object-class-dialog v-model="modal" :entry="entry" @ok="addObjectClass" />
    
    <!-- Modals for footer -->
    <add-attribute-dialog v-model="modal" :entry="entry" :attributes="may"
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
      <div v-else class="control text-xl mr-2" @click="$emit('select-dn')">⊗</div>
    </nav>
    
    <form id="entry" class="space-y-4 my-4" @submit.prevent="save"
        @reset="load(entry.meta.dn)" @focusin="onFocus">
      <form-row v-for="key in keys" class="attr" :key="key"
        :attr="schema.attr(key)" :base-dn="baseDn" :meta="entry.meta" :values="entry.attrs[key]"
        :changed="entry.changed.includes(key)" :structural="schema.structural"
        :may="may.includes(key)" :must="must.includes(key)"
        @display-attr="$emit('display-attr', $event)"
        @display-oc="$emit('display-oc', $event)"
        @form-changed="prepareForm"
        @reload-form="load"
        @valid="valid(key, $event)"
        @show-modal="modal = $event;" />

      <!-- Footer with buttons -->
      <div class="flex ml-4 mt-2 space-x-4">
        <div class="w-1/3"></div>
        <div class="w-2/3 pl-4">
          <div class="w-[90%] space-x-3">
            <button type="submit" class="btn bg-primary"
              accesskey="s" :disabled="invalid.length != 0">Submit</button>
            <button type="reset" v-if="!entry.meta.isNew"
              class="btn bg-secondary">Reset</button>
            <button class="btn float-right bg-secondary" accesskey="a"
              v-if="!entry.meta.isNew" @click="modal = 'add-attribute';">
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
  import CopyEntryDialog from './CopyEntryDialog.vue';
  import DeleteEntryDialog from './DeleteEntryDialog.vue';
  import DiscardEntryDialog from './DiscardEntryDialog.vue';
  import DropdownMenu from '../DropdownMenu.vue';
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
      DropdownMenu,
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
      showInfo: Function,
      schema: Object,
    },

    model: {
      prop: 'activeDn',
      event: 'select-dn'
    },

    inject: [ 'xhr' ],

    data: function() {
      return {
        entry: undefined,    // entry in editor
        focused: undefined,  // currently focused input
        invalid: [],         // field IDs with validation errors
        modal: undefined,    // pop-up dialog
      }
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

      newEntry: function(entry, dn) {
        this.entry = entry;
        this.$emit('select-dn');
        this.prepareForm();
      },

      discardEntry: function(dn) {
        this.entry = null;
        this.$emit('select-dn', dn);
      },

      addAttribute: function(attr) {
        this.$set(this.entry.attrs, attr, ['']);
        this.prepareForm(attr + '-0');
      },

      addObjectClass: function(oc) {
        this.entry.attrs.objectClass.push(oc);
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

      renameEntry: async function(rdn) {
        await this.xhr({
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
        this.$emit('select-dn', dnparts.join(','));
      },

      deleteEntry: async function(dn) {
        if (await this.xhr({ url: 'api/entry/' + dn, method: 'DELETE' }) !== undefined) {
          this.showInfo('Deleted: ' + dn);
          this.$emit('select-dn', '-' + dn);
        }
      },

      changePassword: async function(oldPass, newPass) {
        const data = await this.xhr({
          url: 'api/entry/password/' + this.entry.meta.dn,
          method: 'POST',
          data: JSON.stringify({ old: oldPass, new1: newPass }),
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
        });

        if (data !== undefined) {
          this.$set(this.entry.attrs, 'userPassword', [ data ]);
          this.entry.changed.push('userPassword');
        }
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
