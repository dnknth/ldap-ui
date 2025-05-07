<template>
  <popover :open="show" @update:open="results = []">
    <li v-for="item in results" :key="item.dn" @click="done(item.dn)" :title="label == 'dn' ? '' : trim(item.dn)"
      role="menuitem">
      {{ item[label as keyof Result] }}
    </li>
  </popover>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from 'vue';
import Popover from './ui/Popover.vue';
import type { Provided } from './Provided';
import { search } from '../generated/sdk.gen'
import type { SearchResult } from '../generated/types.gen'

interface Result {
  dn: string;
  name: string;
}

const props = defineProps({
  query: {
    type: String,
    default: '',
  },
  for: String,
  label: {
    type: String,
    default: 'name',
    validator: (value: string) => ['name', 'dn'].includes(value)
  },
  shorten: String,
  silent: {
    type: Boolean,
    default: false,
  },
}),

  app = inject<Provided>('app'),
  results = ref<SearchResult[]>([]),
  show = computed(() => props.query.trim() != ''
    && results.value && results.value.length > 1),
  emit = defineEmits(['select-dn']);

watch(() => props.query, async (q) => {
  if (!q) return;

  const response = await search({ path: { query: q }, client: app?.client });
  if (!response.data) return;
  results.value = await response.data

  if (results.value.length == 0 && !props.silent) {
    app?.showWarning('No search results');
    return;
  }

  if (results.value.length == 1) {
    done(results.value[0].dn);
    return;
  }

  results.value.sort((a: Result, b: Result) =>
    a[props.label as keyof Result].toLowerCase().localeCompare(
      b[props.label as keyof Result].toLowerCase()));
});

function trim(dn: string) {
  return props.shorten && props.shorten != dn
    ? dn.replace(props.shorten, '…') : dn;
}

// use an auto-completion choice
function done(dn: string) {
  emit('select-dn', dn);
  results.value = [];

  nextTick(() => {
    // Return focus to search input
    if (props.for) {
      const el = document.getElementById(props.for);
      if (el) el.focus();
    }
  });
}
</script>
