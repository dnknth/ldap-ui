<template>
  <b-modal id="copy-entry" title="Copy entry"
    @show="reset" @shown="init" @ok="done" @hidden="$emit('update-form')">
    
    <div class="error" v-if="error">{{ error }}</div>
    <input id="copy-to-dn" v-model="dn" class="mb-3 form-control"
        placeholder="New DN" @keyup.enter="done" />
  </b-modal>
</template>

<script>

export default {

  name: 'CopyEntryDialog',

  props: {
    entry: {
      type: Object,
      required: true,
    },
  },

  data: function() {
    return {
      dn: this.entry.meta.dn,
      error: '',
    }
  },

  methods: {

    reset: function() {
      this.dn = this.error = '';
    },

    init: function() {
      document.getElementById('copy-to-dn').focus();
      this.dn = this.entry.meta.dn;
    },

    // Load copied entry into the editor
    done: function(evt) {

      if (!this.dn || this.dn == this.entry.meta.dn) {
        evt.preventDefault();
        this.error = 'This DN already exists';
        return;
      }
      
      const parts = this.dn.split(','),
        rdnpart = parts[0].split('='), 
        rdn = rdnpart[0];

      if (rdnpart.length != 2) {
        evt.preventDefault();
        this.error = 'Invalid RDN: ' + parts[0];
        return;
      }
      
      this.$set(this.entry.attrs, rdn, [rdnpart[1]]);
      this.$set(this.entry.meta, 'dn', this.dn);
      this.$set(this.entry.meta, 'isNew', true);

      this.$bvModal.hide('copy-entry');
      this.$emit('select-dn');
    },

  },
}
</script>

<style scoped>
  div.error {
    color: red;
    font-size: small;
    margin-bottom: 0.3em;
  }
</style>
