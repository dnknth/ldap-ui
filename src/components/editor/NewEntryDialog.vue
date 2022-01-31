<template>
  <b-modal id="new-entry" title="New entry"
    @show="reset" @shown="init" @ok="done" @hidden="$emit('update-form')">
    
    <b-form-group label="Object class:" label-for="newoc">
      <b-form-select id="new-oc" v-model="objectClass" class="mb-3"
        :options="schema.structural">
      </b-form-select>
    </b-form-group>
    
    <b-form-group label="RDN attribute:" label-for="new-rdn" v-if="objectClass">
      <b-form-select id="newrdn" v-model="rdn" :options="rdns()" class="mb-3" />
    </b-form-group>

    <input v-if="objectClass" class="form-control mb-3" v-model="name" id="new-name"
      placeholder="RDN value" @keyup.enter="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'NewEntryDialog',

  props: {
    entry: {
      type: Object,
      required: true,
    },

    schema: {
      type: Object,
      required: true,
    },
},

  data: function() {
    return {
      name: null,
      rdn: null,
      objectClass: null,
    }
  },

  methods: {

    reset: function() {
      this.name = this.rdn = this.objectClass = null;
    },
    
    init: function() {
      document.getElementById('new-oc').focus();
    },

    // Create a new entry in the main editor
    done: function(evt) {
      if (!this.objectClass || !this.rdn || !this.name) {
          evt.preventDefault();
          return;
      }

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
      this.$bvModal.hide('new-entry');
      this.$emit('replace-entry', entry);
      this.$emit('select-dn')
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
