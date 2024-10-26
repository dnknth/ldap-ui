<template>
  <popover :open="show" @update:open="results = []">
    <li v-for="item in results" :key="item.oid" @click="done(item.name!)" :title="item.oid" role="menuitem">
      {{ item.name }}
    </li>
  </popover>
</template>

<script setup lang="ts">
import type { Attribute } from '../schema/schema';
import { computed, inject, nextTick, ref, watch } from 'vue';
import Popover from '../ui/Popover.vue';
import type { Provided } from '../Provided';

const props = defineProps({
  query: { type: String, default: '' },
  for: { type: String, default: '' },
}),
  app = inject<Provided>('app'),
  results = ref<Attribute[]>([]),
  show = computed(() => props.query.trim() != ''
    && results.value
    && results.value.length > 0
    && !(results.value.length == 1 && props.query == results.value[0].name)),
  emit = defineEmits(['done']);

watch(() => props.query,
  (q) => {
    if (!q) return;
    results.value = app?.schema?.search(q) || [];
    results.value.sort((a: Attribute, b: Attribute) =>
      a.name!.toLowerCase().localeCompare(b.name!.toLowerCase()));
  });

// use an auto-completion choice
function done(value: string) {
  emit('done', value);
  results.value = [];

  nextTick(() => {
    // Return focus to search input
    const el = document.getElementById(props.for);
    if (el) el.focus();
  });
}
</script>
