<template>
  <modal title="Are you sure?" :open="modal == 'delete-entry'" :return-to="returnTo" cancel-classes="bg-primary/80"
    ok-classes="bg-danger/80" @show="init" @shown="onShown" @ok="onOk" @cancel="emit('update:modal')">

    <p class="strong">This action is irreversible.</p>

    <div v-if="subtree.length">
      <p class="text-danger mb-2">The following child nodes will be also deleted:</p>
      <div v-for="node in subtree" :key="node.dn">
        <span v-for="i in node.level" class="ml-6" :key="i"></span>
        <node-label :oc="node.structuralObjectClass">
          {{ node.dn.split(',')[0] }}
        </node-label>
      </div>
    </div>

    <template #modal-ok>
      <i class="fa fa-trash-o fa-lg"></i> Delete
    </template>
  </modal>
</template>

<script setup lang="ts">
import { ref, inject } from 'vue';
import Modal from '../ui/Modal.vue';
import NodeLabel from '../NodeLabel.vue';
import type { TreeItem } from '../../generated/types.gen';
import { getSubtree } from '../../generated/sdk.gen';
import type { Provided } from '../Provided'

const props = defineProps({
  dn: { type: String, required: true },
  modal: String,
  returnTo: String,
}),
  subtree = ref<TreeItem[]>([]),
  emit = defineEmits(['ok', 'update:modal']),
  app = inject<Provided>('app');


// List subordinate elements to be deleted
async function init() {
  const response = await getSubtree({
    path: { root_dn: props.dn },
    client: app?.client
  })
  if (response.data) {
    subtree.value = response.data;
  }
}

function onShown() {
  document.getElementById('ui-modal-ok')?.focus();
}

function onOk() {
  emit('update:modal');
  emit('ok', props.dn);
}
</script>
