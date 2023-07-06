<template>
  <div v-if="shown" class="flex mx-4 space-x-4">
    <div :class="{ required: must, optional: may, rdn: isRdn, illegal: illegal }"
      class="w-1/3">
      <span class="cursor-pointer oc" :title="attr.desc"
        @click="$emit('display-attr', attr.name)">{{ attr }}</span>
      <i v-if="changed" class="fa text-emerald-700 ml-1 fa-check"></i>
    </div>

    <div class="w-2/3">
      <div v-for="(val, index) in values" class="attr-value" :key="index">
        <span v-if="isStructural(val)" @click="$emit('show-modal', 'add-object-class')" tabindex="-1"
          class="add-btn control font-bold" title="Add objectClass…">⊕</span>
        <span v-else-if="isAux(val)" @click="removeObjectClass(index)"
          class="remove-btn control" :title="'Remove ' + val">⊖</span>
        <span v-else-if="password" class="fa fa-question-circle control"
          @click="$emit('show-modal', 'change-password')" tabindex="-1" title="change password"></span>
        <span v-else-if="attr == 'jpegPhoto' || attr == 'thumbnailPhoto'"
          @click="$emit('show-modal', 'add-jpegPhoto')" tabindex="-1"
          class="add-btn control align-top" title="Add photo…">⊕</span>
        <span v-else-if="multiple(index)" @click="addRow"
          class="add-btn control" title="Add row">⊕</span>
        <span v-else class="mr-5"></span>

        <span v-if="attr == 'jpegPhoto' || attr == 'thumbnailPhoto'">
          <img v-if="val" :src="'data:image/' + ((attr == 'jpegPhoto') ? 'jpeg' : '*') +';base64,' + val"
            class="max-w-[120px] max-h-[120px] border p-[1px] inline mx-1"/>
          <span v-if="val" class="control remove-btn align-top"
            @click="deleteBlob(index)" title="Remove photo">⊖</span>
        </span>
        <input v-else v-model="values[index]" :id="attr + '-' + index" :type="type"
          class="w-[90%] glyph outline-none bg-back border-x-0 border-t-0 border-b border-solid border-front/20 focus:border-accent px-1"
          :class="{ structural: isStructural(val), auto: defaultValue,
          illegal: illegal || duplicate(index) }"
          :placeholder="placeholder" :disabled="disabled"
          :title="equality == 'generalizedTimeMatch' ? dateString(val) : ''"
          @keyup="search" @keyup.esc="query = ''" @focusin="query = ''" />

        <i v-if="attr == 'objectClass'" class="cursor-pointer fa fa-info-circle"
          @click="$emit('display-oc', val)"></i>
      </div>
      <search-results v-if="completable" @select-dn="complete"
        :for="elementId" :query="query" label="dn" placement="topleft" :shorten="baseDn" />
      <div v-if="hint" class="text-xs pl-2 opacity-70">{{ hint }}</div>
    </div>
  </div>
</template>

<script>
  function unique(element, index, array) {
    return array.indexOf(element) == index;
  }

  import SearchResults from '../SearchResults.vue';

  export default {
    name: 'FormRow',

    components: { SearchResults },

    props: {
      attr: Object,
      values: Array,
      structural: Array,
      meta: Object,
      must: Boolean,
      may: Boolean,
      changed: Boolean,
      baseDn: String,
    },

    inject: [ 'xhr' ],

    data: function() {
      return {
        valid: undefined,

        // Numeric ID ranges
        idRanges:
          [ 'uidNumber', 'gidNumber' ],

        // Range auto-completion
        autoFilled: null,
        hint: '',

        // DN search
        query: '',
        elementId: undefined,
      }
    },

    watch: {
      valid: function(ok) {
        this.$emit('valid', ok);
      }
    },

    created: async function() {
      if (this.disabled
        || !this.idRanges.includes(this.attr.name)
        || this.values.length != 1
        || this.values[0]) return;

      const range = await this.xhr({ url: 'api/range/' + this.attr.name });
      if (!range) return;
      
      this.hint = range.min == range.max
        ? '> ' + range.min
        : '\u2209 (' + range.min + " - " + range.max + ')';
      this.autoFilled = new String(range.next);
      this.$set(this.values, 0, this.autoFilled);
    },

    mounted: function() { this.validate(); },
    updated: function() { this.validate(); },

    methods: {
      validate: function() {
        this.valid = !this.missing
          && (!this.illegal || this.empty)
          && this.values.every(unique);
      },

      // Add an empty row in the entry form
      addRow: function() {
        if (!this.values.includes('')) this.values.push('');
        this.$emit('form-changed', this.attr.name + '-' + (this.values.length -1));
      },

      // Remove a row from the entry form
      removeObjectClass: function(index) {
        const removedOc = this.values.splice(index, 1)[0],
          aux = this.meta.aux.filter(oc => oc < removedOc);
        this.meta.aux.splice(aux.length, 0, removedOc);
        this.$emit('form-changed');
      },

      // human-readable dates
      dateString: function(dt) {
        let tz = dt.substr(14);
        if (tz != 'Z') {
          tz = tz.substr(0, 3) + ':'
            + (tz.length > 3 ? tz.substring(3, 2) : '00');
        }
        return new Date(dt.substr(0, 4) + '-'
          + dt.substr(4, 2) + '-'
          + dt.substr(6, 2) + 'T'
          + dt.substr(8, 2) + ':'
          + dt.substr(10, 2) + ':'
          + dt.substr(12, 2) + tz).toLocaleString(undefined, {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric'
          });
      },

      // Is the given value a structural object class?
      isStructural: function(val) {
        return this.attr.name == 'objectClass' && this.structural.includes(val);
      },

      // Is the given value an auxillary object class?
      isAux: function(val) {
        return this.attr.name == 'objectClass' && !this.structural.includes(val);
      },

      duplicate: function(index) {
        return !unique(this.values[index], index, this.values);
      },

      multiple: function(index) {
        return index == 0
          && !this.attr.single_value
          && !this.disabled
          && !this.values.includes('');
      },

      // auto-complete form values
      search: function(evt) {
        this.elementId = evt.target.id;
        const q = evt.target.value;
        this.query = q.length >= 2 && !q.includes(',') ? q : '';
      },

      // use an auto-completion choice
      complete: function(dn) {
        const index = +this.elementId.split('-')[1];
        this.$set(this.values, index, dn);
        this.query = '';
      },
      
      // remove an image
      deleteBlob: async function(index) {
        const data = await this.xhr({
          method: 'DELETE',
          url:  'api/blob/' + this.attr.name + '/' + index + '/' + this.meta.dn,
        });
        
        if (data) this.$emit('reload-form', this.meta.dn, data.changed);
      },
    },

    computed: {
      shown: function() {
        return (this.attr.name == 'jpegPhoto' || this.attr.name == 'thumbnailPhoto')
          || (!this.attr.no_user_mod && !this.binary);
      },

      equality: function() { return this.attr.getField('equality'); },
      password: function() { return this.attr.name == 'userPassword'; },

      binary: function() {
        return this.password ? false // Corner case with octetStringMatch
          : this.meta.binary.includes(this.attr.name);                    
      },
      
      disabled: function() {
        return this.isRdn
          || this.attr.name == 'objectClass'
          || (!this.meta.isNew && (this.password || this.binary));
      },

      completable: function() {
        return this.elementId && this.equality == 'distinguishedNameMatch';
      },

      placeholder: function() {
        if (this.completable) return '\uf002'; // fa-search
        if (this.missing) return '\uf071';     // fa-warning
        if (this.empty) return '\uf1f8';       // fa-trash
        return undefined;
      },

      isRdn: function() { return this.attr.name == this.meta.dn.split('=')[0]; },

      // Guess the <input> type for an attribute
      type: function() {
        if (this.password) return 'password';
        if (this.equality == 'integerMatch') return 'number';
        return 'text';
      },

      defaultValue: function() {
        return this.values.length == 1 && this.values[0] == this.autoFilled;
      },

      empty: function() { return this.values.every(value => !value.trim()); },
      missing: function() { return this.empty && this.must; },
      illegal: function() { return !this.must && !this.may; }

    },
  }
</script>

<style scoped>
  div.optional span.oc {
    @apply text-front/70;
  }

  div.illegal, input.illegal {
    @apply line-through text-danger;
  }

  div.rdn span.oc, input.structural {
    font-weight: bold;
  }

  .add-btn, .remove-btn, .fa-info-circle, .fa-question-circle {
    @apply opacity-40 hover:opacity-70 text-base;
  }
  
  input.disabled, input:disabled {
    @apply border-b-0;
  }

  input.auto {
    @apply text-accent;
  }

  div.rdn span.oc::after {
    content: ' (rdn)';
    font-weight: 200;
  }
</style>
