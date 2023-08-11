<template>
  <card v-if="modelValue" :title="attr.names.join(', ')" @close="$emit('update:modelValue')">

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
          <span class="cursor-pointer" @click="$emit('update:modelValue', name)">{{ name }}</span>
        </li>
      </ul>
    </div>
  </card>
</template>

<script>
  import Card from '../ui/Card.vue';

  export default {
    name: 'AttributeCard',

    components: {
      Card,
    },

    props: {
      modelValue: String,
    },

    inject: [ 'app' ],

    data: function() {
      return {
        hiddenFields: [         // not shown in schema panel
          'desc', 'name', 'names',
          'no_user_mod', 'obsolete', 'oid',
          'usage', 'syntax', 'sup' ]
      };
    },

    computed: {
      attr: function() {
        return this.modelValue ? this.app.schema.attr(this.modelValue) : undefined;
      },
    },
  }
</script>
