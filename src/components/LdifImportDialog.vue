<template>
  <modal title="Import" :open="modal == 'ldif-import'" ok-title="Import"
    @show="init" @ok="onOk" @cancel="$emit('close')">
    
    <textarea v-model="ldifData" id="ldif-data" placeholder="Paste or upload LDIF">
    </textarea>
    
    <input type="file" value="Upload…" @change="upload" accept=".ldif" />
  </modal>
</template>

<script>
  import Modal from './Modal.vue';

  export default {
    name: 'LdifImportDialog',

    components: {
      Modal,
    },

    inject: [ 'xhr' ],

    props: {
      modal: String,
    },

    model: {
      prop: 'modal',
      event: 'close',
    },

    data: function() {
      return {
        ldifData: '',
        ldifFile: null,
      }
    },

    methods: {
      init: function() {
        this.ldifData = '';
        this.ldifFile = null;
      },
      
      // Load LDIF from file
      upload: function(evt) {
        const file = evt.target.files[0],
            reader = new FileReader(),
            vm = this;
        reader.onload = function() {
          vm.ldifData = reader.result;
          evt.target.value = null;
        }
        reader.readAsText(file);
      },
      
      // Import LDIF
      onOk: async function() {
        if (!this.ldifData) {
          return;
        }

        this.$emit('close');
        const xhr = await this.xhr({
          url: 'api/ldif',
          method: 'POST',
          data: this.ldifData,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });

        if (xhr) this.$emit('ok', '-');
      },
    },
  }
</script>
