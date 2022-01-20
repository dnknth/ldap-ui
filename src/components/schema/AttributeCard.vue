<template>
  <b-card v-if="attr" :title="attr.desc" title-tag="strong">
    <span class="header" slot="header">
      {{ attr.names.join(', ') }}
      <span class="control close-box" @click="$emit('display-attr')">⊗</span>
    </span>
    
    <ul>
      <template v-for="(val, key) in attr">
        <li :key="key" v-if="val &amp;&amp; hiddenFields.indexOf(key) == -1">
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

import { LdapSchema } from './schema.js'

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
  span.header {
    font-weight: bold;
  }
</style>
