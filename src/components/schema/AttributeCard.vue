<template>
  <card :title="attr.names.join(', ')" @close="$emit('display-attr')">

    <div class="header">{{ attr.desc }}</div>
    
    <ul class="list-disc mt-2">
      <template v-for="(val, key) in attr">
        <li :key="key" v-if="val && hiddenFields.indexOf(key) == -1">
          {{ key }}: {{ val }}
        </li>
      </template>
    </ul>
    
    <div v-if="attr.sup.length > 0" class="mt-2"><i>Parents:</i>
      <ul class="list-disc mt-2">
        <li v-for="name in attr.sup" :key="name">
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
    name: 'AttributeCard',

    components: {
      Card,
    },

    props: {
      attr: LdapSchema.Attribute,
    },

    data: function() {
      return {
        hiddenFields: [         // not shown in schema panel
          'desc', 'name', 'names',
          'no_user_mod', 'obsolete', 'oid',
          'usage', 'syntax', 'sup' ]
      }
    }
  }
</script>
