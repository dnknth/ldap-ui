<template>
  <modal title="Copy entry" :open="modal == 'copy-entry'"
    @show="init" @shown="$refs.dn.focus()"
    @ok="onOk" @cancel="$emit('close')">
    
    <div>
      <div class="text-danger text-xs mb-1" v-if="error">{{ error }}</div>
      <input ref="dn" v-model="dn" placeholder="New DN" @keyup.enter="onOk" />
    </div>
  </modal>
</template>

<script>
  import Modal from '../Modal.vue';

  export default {
    name: 'CopyEntryDialog',

    components: {
      Modal,
    },

    props: {
      entry: Object,
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    data: function() {
      return {
        dn: undefined,
        error: '',
      }
    },

    methods: {

      init: function() {
        this.error = '';
        this.dn = this.entry.meta.dn;
      },

      // Load copied entry into the editor
      onOk: function() {
        if (!this.dn || this.dn == this.entry.meta.dn) {
          this.error = 'This DN already exists';
          return;
        }
        
        const parts = this.dn.split(','),
          rdnpart = parts[0].split('='), 
          rdn = rdnpart[0];

        if (rdnpart.length != 2) {
          this.error = 'Invalid RDN: ' + parts[0];
          return;
        }

        this.$emit('close');
        const entry = JSON.parse(JSON.stringify(this.entry));
        entry.attrs[rdn] = [rdnpart[1]];
        entry.meta.dn = this.dn;
        entry.meta.isNew = true;
        this.$emit('ok', entry);
      },
    },
  }
</script>
