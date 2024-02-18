<template>
  <popover :open="show" @update:open="results = []" @select="done(results[$event].name)">
    <li v-for="item in results" :key="item.oid" @click="done(item.name)"
      :title="item.oid" role="menuitem">
        {{ item.name }}
    </li>
  </popover>
</template>

<script setup>
  import { computed, inject, nextTick, ref, watch } from 'vue';
  import Popover from '../ui/Popover.vue';

  const props = defineProps({
      query: String,
      for: String,
    }),
    app = inject('app'),
    results = ref([]),
    show = computed(() => props.query.trim() != ''
          && results.value
          && results.value.length > 0
          && !(results.value.length == 1 && props.query == results.value[0])),
    emit = defineEmits(['done']);

  watch(() => props.query,
    (q) => {
      if (!q) return;
      results.value = app.schema.search(q);
      results.value.sort((a, b) =>
        a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
  });

  // use an auto-completion choice
  function done(value) {
    emit('done', value);
    results.value = [];

    nextTick(()=> {
      // Return focus to search input
      const el = document.getElementById(props.for);
      if (el) el.focus();
    });
  }
</script>
