<template>
  <div v-if="attr && shown" class="flex mx-4 space-x-4">
    <div :class="{ required: must, optional: may, rdn: isRdn, illegal: illegal }"
      class="w-1/4">
      <span class="cursor-pointer oc" :title="attr.desc"
        @click="emit('show-attr', attr.name)">{{ attr }}</span>
      <i v-if="changed" class="fa text-emerald-700 ml-1 fa-check"></i>
    </div>

    <div class="w-3/4">
      <div v-for="(val, index) in values" :key="index">
        <span v-if="isStructural(val)" @click="emit('show-modal', 'add-object-class')" tabindex="-1"
          class="add-btn control font-bold" title="Add object class…">⊕</span>
        <span v-else-if="isAux(val)" @click="removeObjectClass(index)"
          class="remove-btn control" :title="'Remove ' + val">⊖</span>
        <span v-else-if="password" class="fa fa-question-circle control"
          @click="emit('show-modal', 'change-password')" tabindex="-1" title="change password"></span>
        <span v-else-if="attr == 'jpegPhoto' || attr == 'thumbnailPhoto'"
          @click="emit('show-modal', 'add-jpegPhoto')" tabindex="-1"
          class="add-btn control align-top" title="Add photo…">⊕</span>
        <span v-else-if="multiple(index) && !illegal" @click="addRow"
          class="add-btn control" title="Add row">⊕</span>
        <span v-else class="mr-5"></span>

        <span v-if="attr == 'jpegPhoto' || attr == 'thumbnailPhoto'">
          <img v-if="val" :src="'data:image/' + ((attr == 'jpegPhoto') ? 'jpeg' : '*') +';base64,' + val"
            class="max-w-[120px] max-h-[120px] border p-[1px] inline mx-1"/>
          <span v-if="val" class="control remove-btn align-top ml-1"
            @click="deleteBlob(index)" title="Remove photo">⊖</span>
        </span>
        <input v-else :value="values[index]" :id="attr + '-' + index" :type="type"
          class="w-[90%] glyph outline-none bg-back border-x-0 border-t-0 border-b border-solid border-front/20 focus:border-primary px-1"
          :class="{ structural: isStructural(val), auto: defaultValue, illegal: (illegal && !empty) || duplicate(index) }"
          :placeholder="placeholder" :disabled="disabled"
          :title="attr.equality == 'generalizedTimeMatch' ? dateString(val) : ''"
          @input="update" @focusin="query = ''"
          @keyup="search" @keyup.esc="query = ''" />

        <i v-if="attr == 'objectClass'" class="cursor-pointer fa fa-info-circle"
          @click="emit('show-oc', val)"></i>
      </div>
      <search-results silent v-if="completable && elementId" @select-dn="complete"
        :for="elementId" :query="query" label="dn" :shorten="baseDn" />
      <div v-if="hint" class="text-xs ml-6 opacity-70">{{ hint }}</div>
    </div>
  </div>
</template>

<script setup>
  import { computed, inject, onMounted, onUpdated, ref, watch } from 'vue';
  import SearchResults from '../SearchResults.vue';

  function unique(element, index, array) {
    return element == '' || array.indexOf(element) == index;
  }

  const dateFormat = {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric'
    },
    
    idRanges = ['uidNumber', 'gidNumber'], // Numeric ID ranges

    props = defineProps({
      attr: { type: Object, required: true },
      baseDn: String,
      values: { type: Array, required: true },
      meta: { type: Object, required: true },
      must: { type: Boolean, required: true },
      may: { type: Boolean, required: true },
      changed: { type: Boolean, required: true },
    }),

    app = inject('app'),

    valid = ref(true),

    // Range auto-completion
    autoFilled = ref(null),
    hint = ref(''),

    // DN search
    query = ref(''),
    elementId = ref(null),

    completable = computed(() => props.attr.equality == 'distinguishedNameMatch'),
    defaultValue = computed(() => props.values.length == 1 && props.values[0] == autoFilled.value),
    empty = computed(() => props.values.every(value => !value.trim())),
    illegal = computed(() => !props.must && !props.may),
    isRdn = computed(() => props.attr.name == props.meta.dn.split('=')[0]),
    missing = computed(() => empty.value && props.must),
    password = computed(() => props.attr.name == 'userPassword'),

    binary = computed(() =>
      password.value ? false // Corner case with octetStringMatch
        : props.meta.binary.includes(props.attr.name)),
    
    disabled = computed(() => isRdn.value
        || props.attr.name == 'objectClass'
        || (illegal.value && empty.value)
        || (!props.meta.isNew && (password.value || binary.value))),

    placeholder = computed(() => {
      let symbol = '';
      if (completable.value) symbol = ' \uf002 '; // fa-search
      if (missing.value) symbol = ' \uf071 ';     // fa-warning
      if (empty.value) symbol = ' \uf1f8 ';       // fa-trash
      return symbol;
    }),

    shown = computed(() =>
        props.attr.name == 'jpegPhoto'
          || props.attr.name == 'thumbnailPhoto'
          || (!props.attr.no_user_mod && !binary.value)),

    type = computed(() => {
      // Guess the <input> type for an attribute
      if (password.value) return 'password';
      return props.attr.equality == 'integerMatch' ? 'number' : 'text';
    }),

    emit = defineEmits(['reload-form', 'show-attr', 'show-modal', 'show-oc', 'update', 'valid']);

  watch(valid, (ok) => emit('valid', ok));
  
  onMounted(async () => {
    // Auto-fill ranges
    if (disabled.value
      || !idRanges.includes(props.attr.name)
      || props.values.length != 1
      || props.values[0]) return;

    const range = await app.xhr({ url: 'api/range/' + props.attr.name });
    if (!range) return;
    
    hint.value = range.min == range.max
      ? '> ' + range.min
      : '\u2209 (' + range.min + " - " + range.max + ')';
    autoFilled.value = new String(range.next);
    emit('update', props.attr.name, [autoFilled.value], 0);
    validate();
  })

  onUpdated(validate);

  function validate() {
    valid.value = !missing.value
      && (!illegal.value || empty.value)
      && props.values.every(unique);
  }

  function update(evt) {
    const value = evt.target.value,
      index = +evt.target.id.split('-')[1];
    let values = props.values.slice();
    values[index] = value;
    emit('update', props.attr.name, values);
  }

  // Add an empty row in the entry form
  function addRow() {
    let values = props.values.slice();
    if (!values.includes('')) values.push('');
    emit('update', props.attr.name, values, values.length - 1);
  }

  // Remove a row from the entry form
  function removeObjectClass(index) {
    let values = props.values.slice(0, index).concat(props.values.slice(index + 1));
    emit('update', 'objectClass', values);
  }

  // human-readable dates
  function dateString(dt) {
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
      + dt.substr(12, 2) + tz).toLocaleString(undefined, dateFormat);
  }

  // Is the given value a structural object class?
  function isStructural(val) {
    return props.attr.name == 'objectClass' && app.schema.oc(val).structural;
  }

  // Is the given value an auxillary object class?
  function isAux(val) {
    return props.attr.name == 'objectClass' && !app.schema.oc(val).structural;
  }

  function duplicate(index) {
    return !unique(props.values[index], index, props.values);
  }

  function multiple(index) {
    return index == 0
      && !props.attr.single_value
      && !disabled.value
      && !props.values.includes('');
  }

  // auto-complete form values
  function search(evt) {
    elementId.value = evt.target.id;
    const q = evt.target.value;
    query.value = q.length >= 2 && !q.includes(',') ? q : '';
  }

  // use an auto-completion choice
  function complete(dn) {
    const index = +elementId.value.split('-')[1];
    let values = props.values.slice();
    values[index] = dn;
    query.value = '';
    emit('update', props.attr.name, values);
  }
  
  // remove an image
  async function deleteBlob(index) {
    const data = await app.xhr({
      method: 'DELETE',
      url:  'api/blob/' + props.attr.name + '/' + index + '/' + props.meta.dn,
    });
    
    if (data) emit('reload-form', props.meta.dn, data.changed);
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
    @apply text-primary;
  }

  div.rdn span.oc::after {
    content: ' (rdn)';
    font-weight: 200;
  }
</style>
