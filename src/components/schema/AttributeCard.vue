<template>
  <card v-if="modelValue" :title="attr.names.join(', ')" class="ml-4" @close="emit('update:modelValue')">

    <div class="header">{{ attr.desc }}</div>
    
    <ul class="list-disc mt-2">
      <li v-if="attr.$super">Parent:
        <span class="cursor-pointer"
          @click="emit('update:modelValue', attr.$super.name)">{{ attr.$super }}</span>
      </li>
      <li v-if="attr.equality">Equality: {{ attr.equality }}</li>
      <li v-if="attr.ordering">Ordering: {{ attr.ordering }}</li>
      <li v-if="attr.substr">Substring: {{ attr.substr }}</li>
      <li>Syntax: {{ attr.$syntax }} <span v-if="attr.binary">(binary)</span></li>
    </ul>
  </card>
</template>

<script setup>
  import { computed, inject } from 'vue';
  import Card from '../ui/Card.vue';

  const props = defineProps({ modelValue: String }),
    app = inject('app'),
    attr = computed(() => app.schema.attr(props.modelValue)),
    emit = defineEmits(['show-attr', 'update:modelValue']);
</script>
