<template>
  <b-modal id="rename-entry" title="Rename entry"
    @show="reset" @shown="init" @ok="done" @hidden="$emit('update-form')">
    
    <b-form-group label="New RDN attribute:" label-for="rename-rdn">
      <b-form-select id="rdn" v-model="rdn" :options="rdns" class="mb-3"
        @keydown.native.enter.prevent="done" />
    </b-form-group>
  </b-modal>
</template>

<script>

export default {

  name: 'RenameEntryDialog',

  props: {
    entry: {
      type: Object,
      required: true,
    },
    dn: {
      type: String,
      required: true,
    },
    info: {
      type: Function,
      required: true,
    },
  },

  inject: [ 'getSchema', 'xhr' ],

  data: function() {
    return {
      rdn: undefined,
      schema: this.getSchema(),
    }
  },

  methods: {

    reset: function() {
      this.rdn = undefined;
    },

    init: function() {
      document.getElementById('rdn').focus();
      if (this.rdns.length == 1) this.rdn = this.rdns[0];
    },

    done: async function(evt) {
      const rdnAttr = this.entry.attrs[this.rdn];
      if (!rdnAttr || !rdnAttr[0]) {
        evt.preventDefault();
        return;
      }
      
      const rdn = this.rdn + '=' + rdnAttr[0],
        xhr = await this.xhr({ url: 'api/rename/' + rdn + '/' + this.dn });
      if (!xhr) {
        evt.preventDefault();
        return;
      }

      const dnparts = this.dn.split(',');
      dnparts.splice(0, 1, rdn);

      this.info('👍 Saved changes');
      this.$emit('select-dn', dnparts.join(','));
      this.$bvModal.hide('rename-entry');
    },

    ok: function(key) {
      const rdn = this.entry.meta.dn.split('=')[0];
      return key != rdn && !this.entry.attrs[key].every(val => !val);
    },
  },

  computed: {
    rdns: function() {
      return Object.keys(this.entry.attrs).filter(a => this.ok(a));
    },
    
  }
}
</script>
