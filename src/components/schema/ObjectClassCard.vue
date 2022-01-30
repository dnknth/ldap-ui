<template>
  <b-card v-if="oc" :title="oc.desc" title-tag="strong" class="oc-card">
    <span class="header" slot="header">
      {{ oc.name }}
      <span class="control close-box" @click="$emit('display-oc', undefined)">⊗</span>
    </span>
                
    <div v-if="oc.must.length"> Required attributes:
      <ul>
        <li v-for="name in oc.must" :key="name">
          <span class="clickable u" @click="$emit('display-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.may.length"> Optional attributes:
      <ul>
        <li v-for="name in oc.may" :key="name">
          <span class="clickable u" @click="$emit('display-attr', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.sup.length"> Superclasses:
      <ul>
        <li v-for="name in oc.sup" :key="name">
          <span class="clickable u" @click="$emit('display-oc', name)">{{ name }}</span>
        </li>
      </ul>
    </div>
  </b-card>
</template>

<script>

import { LdapSchema } from './schema.js'

export default {

  name: 'ObjectClassCard',

  props: {
    oc: {
      type: LdapSchema.ObjectClass,
      required: true,
    }
  },
}
</script>

<style scoped>
  span.header {
    font-weight: bold;
  }
</style>
