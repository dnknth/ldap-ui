<template>
  <popover :open="show" @update:open="results = []">
    <li v-for="item in results" :key="item.dn" @click="done(item.dn)"
      :title="label == 'dn' ? '' : trim(item.dn)" role="menuitem">
        {{ item[label] }}
    </li>
  </popover>
</template>

<script setup>
  import { computed, inject, nextTick, ref, watch } from 'vue';
  import Popover from './ui/Popover.vue';

  const props = defineProps({
      query: String,
      for: String,
      label: {
        type: String,
        default: 'name',
        validator: value => ['name', 'dn' ].includes(value)
      },
      shorten: String,
      silent: {
        type: Boolean,
        default: false,
      },
    }),
    app = inject('app'),
    results = ref([]),
    show = computed(() => props.query.trim() != ''
          && results.value && results.value.length > 1),
    emit = defineEmits(['select-dn']);

  watch(() => props.query,
    async (q) => {
      if (!q) return;

      results.value = await app.xhr({ url: 'api/search/' + q });
      if (!results.value) return; // app.xhr failed

      if (results.value.length == 0 && !props.silent) {
        app.showWarning('No search results');
        return;
      }

      if (results.value.length == 1) {
        done(results.value[0].dn);
        return;
      }

      results.value.sort((a, b) =>
        a[props.label].toLowerCase().localeCompare(
          b[props.label].toLowerCase()));
  });

  function trim(dn) {
    return props.shorten && props.shorten != dn
      ? dn.replace(props.shorten, '…') : dn;
  }

  // use an auto-completion choice
  function done(dn) {
    emit('select-dn', dn);
    results.value = [];

    nextTick(()=> {
      // Return focus to search input
      const el = document.getElementById(props.for);
      if (el) el.focus();
    });
  }
</script>
