<template>
  <card v-if="modelValue" :title="attr.names.join(', ')" @close="$emit('update:modelValue')">

    <div class="header">{{ attr.desc }}</div>
    
    <ul class="list-disc mt-2">
      <li v-if="attr.$super">Parent:
        <span class="cursor-pointer"
          @click="$emit('update:modelValue', attr.$super.name)">{{ attr.$super }}</span>
      </li>
      <li v-if="attr.equality">Equality: {{ attr.equality }}</li>
      <li v-if="attr.ordering">Ordering: {{ attr.ordering }}</li>
      <li v-if="attr.substr">Substring: {{ attr.substr }}</li>
      <li>Syntax: {{ attr.$syntax }} <span v-if="attr.binary">(binary)</span></li>
    </ul>
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
