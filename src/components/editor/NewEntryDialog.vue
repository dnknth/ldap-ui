<template>
  <modal title="New entry" :open="modal == 'new-entry'" :return-to="returnTo"
    @ok="onOk" @cancel="emit('update:modal')"
    @show="init" @shown="select.focus()">
    
    <label>Object class:
      <select ref="select" v-model="objectClass">
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

<script setup>
  import { computed, inject, ref } from 'vue';
  import Modal from '../ui/Modal.vue';

  const props = defineProps({
      dn: { type: String, required: true },
      modal: String,
      returnTo: String,
    }),
    app = inject('app'),
    objectClass = ref(null),
    rdn = ref(null),
    name = ref(null),
    select = ref(null),
    oc = computed(() => app.schema.oc(objectClass.value)),
    emit = defineEmits(['ok', 'update:modal']);

  function init() {
    objectClass.value = rdn.value = name.value = null;
  }

      // Create a new entry in the main editor
  function onOk() {
    if (!objectClass.value || !rdn.value || !name.value) return;

    emit('update:modal');

    const objectClasses = [objectClass.value];
    for (let o = oc.value.$super; o; o = o.$super) {
      if (!o.structural && o.kind != 'abstract') {
          objectClasses.push(o.name);
      }
    }
    
    const entry = {
      meta: {
        dn: rdn.value + '=' + name.value + ',' + props.dn,
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
    entry.attrs[rdn.value] = [name.value];
    emit('ok', entry);
  }
  
  // Choice list of RDN attributes for a new entry
  function rdns() {
    if (!objectClass.value) return [];
    const ocs = oc.value.$collect('must');
    if (ocs.length == 1) rdn.value = ocs[0];
    return ocs;
  }
</script>
