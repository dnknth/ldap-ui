<template>
  <card v-if="modelValue" :title="oc.name" @close="$emit('update:modelValue')">
    <div class="header">{{ oc.desc }}</div>
    
    <div v-if="oc.sup.length" class="mt-2"><i>Superclasses:</i>
      <ul class="list-disc">
        <li v-for="name in oc.sup" :key="name">
          <span class="cursor-pointer" @click="$emit('update:modelValue', name)">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.$collect('must').length" class="mt-2"><i>Required attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.$collect('must')" :key="name">
          <span class="cursor-pointer" @click="app.attr = name;">{{ name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="oc.$collect('may').length" class="mt-2"><i>Optional attributes:</i>
      <ul class="list-disc">
        <li v-for="name in oc.$collect('may')" :key="name">
          <span class="cursor-pointer" @click="app.attr = name;">{{ name }}</span>
        </li>
      </ul>
    </div>

  </card>
</template>

<script>
  import Card from '../ui/Card.vue';

  export default {
    name: 'ObjectClassCard',

    components: {
      Card,
    },

    props: {
      modelValue: String,
    },

    inject: [ 'app' ],

    computed: {
      oc: function() {
        return this.modelValue ? this.app.schema.oc(this.modelValue) : undefined;
      },
    },
}
</script>
