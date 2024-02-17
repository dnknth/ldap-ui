<template>
  <card v-if="modelValue" :title="oc.name" class="ml-4" @close="emit('update:modelValue')">
    <div class="header">{{ oc.desc }}</div>
    
    <div v-if="oc.sup.length" class="mt-2"><i>Superclasses:</i>
      <ul class="list-disc">
        <li v-for="name in oc.sup" :key="name">
          <span class="cursor-pointer" @click="emit('update:modelValue', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.$collect('must').length" class="mt-2"><i>Required attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.$collect('must')" :key="name">
          <span class="cursor-pointer" @click="emit('show-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.$collect('may').length" class="mt-2"><i>Optional attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.$collect('may')" :key="name">
          <span class="cursor-pointer" @click="emit('show-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

  </card>
</template>

<script setup>
  import { computed, inject } from 'vue';
  import Card from '../ui/Card.vue';

  const props = defineProps({ modelValue: String }),
    app = inject('app'),
    oc = computed(() => app.schema.oc(props.modelValue)),
    emit = defineEmits(['show-attr', 'show-oc', 'update:modelValue']);
</script>
