<template>
  <modal title="New entry" :open="modal == 'new-entry'"
    @ok="onOk" @cancel="$emit('update:modal')"
    @show="init" @shown="$refs.oc.focus()">
    
    <label>Object class:
      <select ref="oc" v-model="objectClass">
        <template v-for="cls in app.schema.ObjectClass.values" :key="cls.name">
          <option v-if="cls.structural">{{ cls }}</option>
        </template>
      </select>
    </label>
    
    <label v-if="objectClass">RDN attribute:
      <select v-model="rdn">
        <option v-for="rdn in rdns()" :key="rdn">
          {{ rdn }}
        </option>
      </select>
    </label>

    <input v-if="objectClass" v-model="name"
      placeholder="RDN value" @keyup.enter="onOk" />
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'NewEntryDialog',

    components: {
      Modal,
    },
    
    props: {
      dn: {
        type: String,
        required: true,
      },
      modal: String,
    },

    inject: [ 'app' ],

    data: function() {
      return {
        objectClass: null,
        rdn: null,
        name: null,
      };
    },

    methods: {

      init: function() {
        this.objectClass = this.rdn = this.name = null;
      },

      // Create a new entry in the main editor
      onOk: function() {
        if (!this.objectClass || !this.rdn || !this.name) return;

        this.$emit('update:modal');

        const objectClasses = [this.objectClass];
        for (let oc = this.oc.$super; oc; oc = oc.$super) {
          if (!oc.structural && oc.kind != 'abstract') {
              objectClasses.push(oc.name);
          }
        }
        
        const entry = {
          meta: {
            dn: this.rdn + '=' + this.name + ',' + this.dn,
            aux: [],
            required: [],
            binary: [],
            hints: {},
            autoFilled: [],
            isNew: true,
          },
          attrs: {
            objectClass: objectClasses,
          },
          changed: [],
        };
        entry.attrs[this.rdn] = [this.name];
        this.$emit('ok', entry);
      },
      
      // Choice list of RDN attributes for a new entry
      rdns: function() {
        if (!this.objectClass) return [];
        const ocs = this.oc.$collect('must');
        if (ocs.length == 1) this.rdn = ocs[0];
        return ocs;
      },
    },

    computed: {
      oc: function() {
        return this.app.schema.oc(this.objectClass);
      },
    },
  }
</script>
