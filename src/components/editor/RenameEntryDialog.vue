<template>
  <modal title="Rename entry" :open="modal == 'rename-entry'"
    @ok="onOk" @cancel="$emit('update:modal')"
    @show="init" @shown="$refs.rdn.focus()">
    
    <label>New RDN attribute:
      <select ref="rdn" v-model="rdn" @keyup.enter="onOk">
        <option v-for="rdn in rdns" :key="rdn">{{ rdn }}</option>
      </select>
    </label>
  </modal>
</template>

<script>
  import Modal from '../ui/Modal.vue';

  export default {
    name: 'RenameEntryDialog',

    components: {
      Modal,
    },

    props: {
      entry: Object,
      modal: String,
    },

    data: function() {
      return {
        rdn: undefined,
      };
    },

    methods: {
      init: function() {
        this.rdn = this.rdns.length == 1 ? this.rdns[0] : undefined;
      },

      onOk: async function() {
        const rdnAttr = this.entry.attrs[this.rdn];
        if (!rdnAttr || !rdnAttr[0]) {
          return;
        }
        
        this.$emit('update:modal');
        const rdn = this.rdn + '=' + rdnAttr[0];
        this.$emit('ok', rdn);
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
