<template>
  <b-modal id="ldif-import" title="Import" ok-title="Import" @show="reset" @ok="done">
    <textarea v-model="ldifData" class="mb-3 form-control"
        id="ldif-data" placeholder="Paste or upload LDIF">
    </textarea>
    <input type="file" value="Upload…" @change="upload" accept=".ldif" />
  </b-modal>
</template>

<script>

export default {

  name: 'LdifImportDialog',

  inject: [ 'xhr' ],

  data: function() {
    return {
      ldifData: '',
      ldifFile: null,
    }
  },

  methods: {

    reset: function() {
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
    done: async function(evt) {
      if (!this.ldifData) {
        evt.preventDefault();
        return;
      }

      const xhr = await this.xhr({
        url: 'api/ldif',
        method: 'POST',
        data: this.ldifData,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });

      if (xhr) this.$emit('select-dn', '-');
    },
  },
}
</script>

<style scoped>
</style>
