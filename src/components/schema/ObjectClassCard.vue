<template>
  <card :title="oc.name" @close="$emit('display-oc')">
    <div class="header">{{ oc.desc }}</div>
    
    <div v-if="oc.sup.length" class="mt-2"><i>Superclasses:</i>
      <ul class="list-disc">
        <li v-for="name in oc.sup" :key="name">
          <span class="cursor-pointer" @click="$emit('display-oc', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.must.length" class="mt-2"><i>Required attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.must" :key="name">
          <span class="cursor-pointer" @click="$emit('display-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.may.length" class="mt-2"><i>Optional attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.may" :key="name">
          <span class="cursor-pointer" @click="$emit('display-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

  </card>
</template>

<script>
  import { LdapSchema } from './schema.js';
  import Card from '../Card.vue';

  export default {
    name: 'ObjectClassCard',

    components: {
      Card,
    },

    props: {
      oc: LdapSchema.ObjectClass,
    },
  }
</script>
