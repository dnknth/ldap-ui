<template>
  <modal title="New entry" :open="modal == 'new-entry'"
    @ok="onOk" @cancel="$emit('close')"
    @show="init" @shown="$refs.oc.focus()">
    
    <label>Object class:
      <select ref="oc" v-model="objectClass">
        <option v-for="cls in schema.structural">
          {{ cls }}
        </option>
      </select>
    </label>
    
    <label v-if="objectClass">RDN attribute:
      <select v-model="rdn">
        <option v-for="rdn in rdns()">
          {{ rdn }}
        </option>
      </select>
    </label>

    <input v-if="objectClass" v-model="name"
      placeholder="RDN value" @keyup.enter="onOk" />
  </modal>
</template>

<script>
  import Modal from '../Modal.vue';

  export default {
    name: 'NewEntryDialog',

    components: {
      Modal,
    },
    
    props: {
      entry: Object,
      schema: Object,
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    data: function() {
      return {
        objectClass: null,
        rdn: null,
        name: null,
      }
    },

    methods: {

      init: function() {
        this.objectClass = this.rdn = this.name = null;
      },

      // Create a new entry in the main editor
      onOk: function() {
        if (!this.objectClass || !this.rdn || !this.name) {
            return;
        }

        this.$emit('close');

        const entry = {
          meta: {
            dn: this.rdn + '=' + this.name + ',' + this.entry.meta.dn,
            aux: [],
            required: [],
            binary: [],
            hints: {},
            autoFilled: [],
            isNew: true,
          },
          attrs: {
            objectClass: [ this.objectClass ].concat(
              this.oc.superClasses
              .filter(oc => !oc.isStructural && oc.kind != 'abstract')
              .map(oc => oc.name)),
          },
          changed: [],
        };
        entry.attrs[this.rdn] = [this.name];
        this.$emit('ok', entry);
      },
      
      // Choice list of RDN attributes for a new entry
      rdns: function() {
        if (!this.objectClass) return [];
        const ocs = this.oc.getAttributes('must');
        if (ocs.length == 1) this.rdn = ocs[0];
        return ocs;
      },
    },

    computed: {
      oc: function() {
        return this.schema.oc(this.objectClass);
      },
    },
  }
</script>
