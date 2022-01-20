<template>
  <tr v-if="shown">
    <th :class="{ required: required, optional: !required, rdn: isRdn }">
      <span class="clickable oc" :title="attr.desc"
        @click="$emit('display-attr', attr.name)">{{ attr }}</span>
      <i v-if="changed" class="fa green fa-check"></i>
      <span v-if="attr == 'objectClass'" v-b-modal.add-oc
        class="clickable right control add-btn">⊕</span>
      <span v-else-if="attr == 'jpegPhoto'" v-b-modal.upload-photo
        class="clickable right control add-btn">⊕</span>
      <span v-else-if="multiple" @click="addRow"
        class="clickable right control add-btn">⊕</span>
    </th>
    <td>
      <div v-for="(val, index) in values" class="attr-value" :key="index">
        <span v-if="attr == 'jpegPhoto'" class="photo">
          <img v-if="val" :src="'data:image/jpeg;base64,' + val" />
          <span v-if="val" class="clickable control remove-btn" @click="deleteBlob(index)">⊖</span>
        </span>
        <input v-else v-model="values[index]" :id="attr + '-' + index" :type="type" 
          :placeholder="flagged ? '\uf071' : ''" :class="{ structural: isStructural(val),
            disabled: disabled, auto: defaultValue, flagged: flagged }"
          :title="equality == 'generalizedTimeMatch' ? dateString(val) : ''"
          @keyup="complete" @keyup.esc="query = ''" @focusin="query = ''" />
        <i v-if="attr == 'objectClass'" class="clickable fa fa-info-circle"
          @click="$emit('display-oc', val)"></i>
        <i v-if="password" class="clickable fa fa-question-circle"
          v-b-modal.change-password></i>
      </div>
      <auto-completion v-if="completable" :attr="attr.name"
        :index="completeIndex" :query="query" v-model="values" />
      <div v-if="hint" class="hint">{{ hint }}</div>
    </td>
  </tr>
</template>

<script>

import AutoCompletion from './AutoCompletion.vue';

export default {
  components: { AutoCompletion },

  name: 'FormRow',

  props: {
    attr: {
      type: Object,
      required: true,
    },

    values: {
      type: Array,
      required: true,
    },

    structural: {
      type: Array,
      required: true,
    },

    meta: {
      type: Object,
      required: true,
    },

    required: {
      type: Boolean,
      required: true,
    },

    marked: {
      type: Boolean,
      required: true,
    },

    changed: Boolean,
  },

  model: {
    prop: 'values',
    event: 'update-row',
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      // auto ranges
      idRanges:               // Numeric ID ranges
        [ 'uidNumber', 'gidNumber' ],
      autoFilled: null,
      hint: '',

      // auto completion
      completeIndex: null,
      query: '',
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
    this.values[0] = this.autoFilled = new String(range.next);
  },

  methods: {

    // Add an empty row in the entry form
    addRow: function() {
      let values = Array.from(this.values);
      if (!values.includes('')) values.push('');
      
      this.$emit('update-row', values);
      this.$emit('form-changed', this.attr.name + '-' + (values.length -1));
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

    // auto-complete form values
    complete: function(evt) {

      // Avoid AJAX calls without results
      const dropdownId = evt.target.id,
        q = evt.target.value;

      this.completeIndex = +dropdownId.split('-')[1];
      this.query = q.length > 2 && !q.includes(',') ? q : '';
    },

    // remove an image
    deleteBlob: async function(index) {
      // let values = Array.from(this.values);
      // values[index] = '';
      // this.$emit('update-value', values);

      const data = await this.xhr({
        method: 'DELETE',
        url:  'api/blob/' + this.attr.name + '/' + index + '/' + this.meta.dn,
      });
      
      if (data) this.$emit('reload-form', this.meta.dn, data.changed);
    },
  },

  computed: {

    shown: function() {
      return this.attr.name == 'jpegPhoto'
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
        || (!this.meta.isNew && (this.password || this.binary));
    },

    completable: function() { return this.equality == 'distinguishedNameMatch'; },
    isRdn: function() { return this.attr.name == this.meta.dn.split('=')[0]; },

    // Guess the <input> type for an attribute
    type: function() {
      if (this.password) return 'password';
      if (this.equality == 'integerMatch') return 'number';
      return 'text';
    },

    multiple: function() {
      return !this.attr.single_value
        && !this.disabled
        && !this.values.includes('');
    },

    defaultValue: function() {
      return this.values.length == 1 && this.values[0] == this.autoFilled;
    },

    empty: function() { return this.values.length == 1 && !this.values[0]; },
    missing: function() { return this.empty && this.required; },
    flagged: function() { return this.missing && this.marked; },
  },
}
</script>

<style scoped>
  tr.attr>th, tr.attr>td {
    padding-bottom: 2ex;
  }

  th {
    vertical-align: top;
    position: relative;
    top: 0.5ex;
    padding-right: 0;
  }

  th.optional span.oc {
    color: var(--muted-fg);
  }

  th.rdn span.oc {
    font-weight: bold;
  }

  th i.fa-check {
    margin-left: 0.2em;
  }

  input {
    top: 0.2ex;
    width: 90%;
    padding: 0 0.5em;
    border-top-width: 0;
    border-left-width: 0;
    border-right-width: 0;
    position: relative;
    color: var(--page-fg);
    border-bottom: 1px solid var(--muted-bg);
    background-color: var(--page-bg);
  }

  input:focus {
    border-bottom: 2px solid var(--accent);
    outline: none;
  }

  input.disabled {
    border-bottom-width: 0;
    background-color: var(--body-bg);
    color: var(--body-fg);
  }

  div.attr-value {
    margin: 0.2em 0;
  }

  span.photo img {
    max-width: 120px;
    max-height: 120px;
    border: 1px solid #CCC;
    padding: 2px;
  }

  .add-btn {
    position: relative;
    top: -0.5ex;
  }

  .remove-btn {
    vertical-align: top;
    position: relative;
    top: -0.5ex;
  }

  td i.fa {
    opacity: 0.4;
    margin-right: 0.1em;
    position: relative;
    top: 0.3ex;
  }

  td i.fa:hover {
    opacity: 0.7;
  }

  input.structural {
    font-weight: bold;
  }

  .hint {
    font-size: x-small;
    padding-left: 8px;
    opacity: 0.7;
  }

  input.auto {
    color: var(--accent);
  }

  input.flagged {
    color: red;
    font-family: sans-serif, FontAwesome;
  }
</style>
