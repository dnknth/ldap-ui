<template>
  <b-card v-if="attr" :title="attr.names.join(', ')" title-tag="strong">
    <slot name="header">
      <div class="header">{{ attr.desc }}</div>
      <span class="control close-box" @click="$emit('display-attr')">⊗</span>
    </slot>
    
    <ul>
      <template v-for="(val, key) in attr">
        <li :key="key" v-if="val && hiddenFields.indexOf(key) == -1">
          {{ key }}: {{ val }}
        </li>
      </template>
    </ul>
    
    <div v-if="attr.sup.length > 0">
      Superclasses:
      <ul>
        <li v-for="name in attr.sup" :key="name">
          <span class="clickable u" @click="$emit('display-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>
  </b-card>
</template>

<script>

import { LdapSchema } from './schema.js';

export default {

  name: 'AttributeCard',

  props: {
    attr: {
      type: LdapSchema.Attribute,
      required: true,
    }
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

<style scoped>
  div.header {
    margin-bottom: 1ex;
  }
</style>
