<template>
  <div v-if="attr && shown" class="flex mx-4 space-x-4">
    <div :class="{ required: must, optional: may, rdn: isRdn, illegal: illegal }" class="w-1/4">
      <span class="cursor-pointer oc" :title="attr.desc" @click="emit('show-attr', attr.name)">{{ attr }}</span>
      <i v-if="changed" class="fa text-emerald-700 ml-1 fa-check"></i>
    </div>

    <div class="w-3/4">
      <div v-for="(val, index) in values" :key="index">
        <span v-if="isStructural(val)" @click="emit('show-modal', 'add-object-class')" tabindex="-1"
          class="add-btn control font-bold" title="Add object class…">⊕</span>
        <span v-else-if="isAux(val)" @click="removeObjectClass(index)" class="remove-btn control"
          :title="'Remove ' + val">⊖</span>
        <span v-else-if="password" class="fa fa-question-circle control" @click="emit('show-modal', 'change-password')"
          tabindex="-1" title="change password"></span>
        <span v-else-if="attr.name == 'jpegPhoto' || attr.name == 'thumbnailPhoto'"
          @click="emit('show-modal', 'add-jpegPhoto')" tabindex="-1" class="add-btn control align-top"
          title="Add photo…">⊕</span>
        <span v-else-if="multiple(index) && !illegal" @click="addRow" class="add-btn control" title="Add row">⊕</span>
        <span v-else class="mr-5"></span>

        <span v-if="attr.name == 'jpegPhoto' || attr.name == 'thumbnailPhoto'">
          <img v-if="val" :src="'data:image/' +
            (attr.name == 'jpegPhoto' ? 'jpeg' : '*') +
            ';base64,' +
            val
            " class="max-w-[120px] max-h-[120px] border p-[1px] inline mx-1" />
          <span v-if="val" class="control remove-btn align-top ml-1" @click="doDeleteBlob(index)"
            title="Remove photo">⊖</span>
        </span>
        <span v-else-if="boolean">
          <span v-if="index == 0 && !values[0]" class="control text-lg" @click="updateValue(index, 'FALSE')">⊕</span>
          <span v-else class="pb-1 border-primary focus-within:border-b border-solid">
            <toggle-button :id="attr + '-' + index" :value="values[index]" class="mt-2"
              @update:value="updateValue(index, $event)" />
            <i class="fa fa-trash ml-2 relative -top-0.5 control" @click="updateValue(index, '')"></i>
          </span>
        </span>
        <input v-else :value="values[index]" :id="attr + '-' + index" :type="type" autocomplete="off"
          class="w-[90%] glyph outline-none bg-back border-x-0 border-t-0 border-b border-solid border-front/20 focus:border-primary px-1"
          :class="{
            structural: isStructural(val),
            auto: defaultValue,
            illegal: (illegal && !empty) || duplicate(index),
          }" :placeholder="placeholder" :disabled="disabled" :title="time ? dateString(val) : ''" @input="update"
          @focusin="query = ''" @keyup="search" @keyup.esc="query = ''" />

        <i v-if="attr.name == 'objectClass'" class="cursor-pointer fa fa-info-circle" @click="emit('show-oc', val)"></i>
      </div>
      <search-results silent v-if="completable && elementId" @select-dn="complete" :for="elementId" :query="query"
        label="dn" :shorten="baseDn" />
      <attribute-search v-if="oid && elementId" @done="complete" :for="elementId" :query="query" />
      <div v-if="hint" class="text-xs ml-6 opacity-70">{{ hint }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Attribute, generalizedTime } from "../schema/schema";
import { computed, inject, onMounted, onUpdated, ref, watch } from "vue";
import AttributeSearch from "./AttributeSearch.vue";
import type { Provided } from "../Provided";
import SearchResults from "../SearchResults.vue";
import ToggleButton from "../ui/ToggleButton.vue";
import { getRange, deleteBlob } from "../../generated/sdk.gen";
import type { Entry } from "@/generated";

function unique(
  element: unknown,
  index: number,
  array: Array<unknown>,
): boolean {
  return element == "" || array.indexOf(element) == index;
}

const dateFormat: Intl.DateTimeFormatOptions = {
  weekday: "long",
  year: "numeric",
  month: "long",
  day: "numeric",
  hour: "numeric",
  minute: "numeric",
  second: "numeric",
},
  syntaxes = {
    boolean: "1.3.6.1.4.1.1466.115.121.1.7",
    distinguishedName: "1.3.6.1.4.1.1466.115.121.1.12",
    generalizedTime: "1.3.6.1.4.1.1466.115.121.1.24",
    integer: "1.3.6.1.4.1.1466.115.121.1.27",
    oid: "1.3.6.1.4.1.1466.115.121.1.38",
    telephoneNumber: "1.3.6.1.4.1.1466.115.121.1.50",
  },
  idRanges = ["uidNumber", "gidNumber"], // Numeric ID ranges
  props = defineProps<{
    entry: Entry;
    attr: Attribute;
    baseDn?: string;
    values: string[];
    must: boolean;
    may: boolean;
    changed: boolean;
  }>(),
  app = inject<Provided>("app"),
  valid = ref(true),
  // Range auto-completion
  autoFilled = ref<string>(),
  hint = ref(""),
  // DN search
  query = ref(""),
  elementId = ref<string>(),
  boolean = computed(() => props.attr.syntax == syntaxes.boolean),
  completable = computed(() => props.attr.syntax == syntaxes.distinguishedName),
  defaultValue = computed(
    () => props.values.length == 1 && props.values[0] == autoFilled.value,
  ),
  empty = computed(() => props.values.every((value) => !value.trim())),
  illegal = computed(() => !props.must && !props.may),
  isRdn = computed(() => props.attr.name == props.entry.dn.split("=")[0]),
  oid = computed(() => props.attr.syntax == syntaxes.oid),
  missing = computed(() => empty.value && props.must),
  password = computed(() => props.attr.name == "userPassword"),
  time = computed(() => props.attr.syntax == syntaxes.generalizedTime),
  binary = computed<boolean>(() =>
    password.value
      ? false // Corner case with octetStringMatch
      : props.entry.binary.includes(props.attr.name!),
  ),
  disabled = computed(
    () =>
      isRdn.value ||
      props.attr.name == "objectClass" ||
      (illegal.value && empty.value) ||
      (!props.entry.isNew && (password.value || binary.value)),
  ),
  placeholder = computed(() => {
    if (missing.value) return " \uf071 "; // fa-warning
    if (empty.value) return " \uf1f8 "; // fa-trash
    if (completable.value) return " \uf002 "; // fa-search
    return "";
  }),
  shown = computed(
    () =>
      props.attr.name == "jpegPhoto" ||
      props.attr.name == "thumbnailPhoto" ||
      (!props.attr.no_user_mod && !binary.value),
  ),
  type = computed(() => {
    // Guess the <input> type for an attribute
    if (password.value) return "password";
    if (props.attr.syntax == syntaxes.telephoneNumber) return "tel";
    return props.attr.syntax == syntaxes.integer ? "number" : "text";
  }),
  emit = defineEmits<{
    "show-attr": [name?: string];
    "show-modal": [name: string];
    "show-oc": [name: string];
    "reload-form": [dn?: string, values?: string[], focused?: string];
    update: [attr: string, values: string[], index?: number];
    valid: [ok: boolean];
  }>();

watch(valid, (ok) => emit("valid", ok));

onMounted(async () => {
  // Auto-fill ranges
  if (
    disabled.value ||
    !idRanges.includes(props.attr.name!) ||
    props.values.length != 1 ||
    props.values[0]
  )
    return;

  const response = await getRange({
    path: { attribute: props.attr.name! },
    client: app?.client,
  });
  if (!response.data) return;

  const range = response.data;
  hint.value =
    range.min == range.max
      ? "> " + range.min
      : "\u2209 (" + range.min + " - " + range.max + ")";
  autoFilled.value = "" + range.next;
  emit("update", props.attr.name!, [autoFilled.value], 0);
  validate();
});

onUpdated(validate);

function validate() {
  valid.value =
    !missing.value &&
    (!illegal.value || empty.value) &&
    props.values.every(unique);
}

function update(evt: Event) {
  const target = evt.target as HTMLInputElement;
  const value = target.value,
    index = +target.id.split("-").slice(-1).pop()!;
  updateValue(index, value);
}

function updateValue(index: number, value: string) {
  const values = props.values.slice();
  values[index] = value;
  emit("update", props.attr.name!, values);
}

// Add an empty row in the entry form
function addRow() {
  const values = props.values.slice();
  if (!values.includes("")) values.push("");
  emit("update", props.attr.name!, values, values.length - 1);
}

// Remove a row from the entry form
function removeObjectClass(index: number) {
  const values = props.values
    .slice(0, index)
    .concat(props.values.slice(index + 1));
  emit("update", "objectClass", values);
}

// human-readable dates
function dateString(dt: string) {
  return generalizedTime(dt).toLocaleString(undefined, dateFormat);
}

// Is the given value a structural object class?
function isStructural(val: string) {
  return props.attr.name == "objectClass" && app?.schema?.oc(val)?.structural;
}

// Is the given value an auxillary object class?
function isAux(val: string) {
  const oc = app?.schema?.oc(val);
  return props.attr.name == "objectClass" && oc && !oc.structural;
}

function duplicate(index: number) {
  return !unique(props.values[index], index, props.values);
}

function multiple(index: number) {
  return (
    index == 0 &&
    !props.attr.single_value &&
    !disabled.value &&
    !props.values.includes("")
  );
}

// auto-complete form values
function search(evt: Event) {
  const target = evt.target as HTMLInputElement;
  elementId.value = target.id;
  const q = target.value;
  query.value = q.length >= 2 && !q.includes(",") ? q : "";
}

// use an auto-completion choice
function complete(dn: string) {
  const index = +elementId.value!.split("-").slice(-1).pop()!;
  const values = props.values.slice();
  values[index] = dn;
  query.value = "";
  emit("update", props.attr.name!, values);
}

// remove an image
async function doDeleteBlob(index: number) {
  const response = await deleteBlob({
    path: { attr: props.attr.name!, index, dn: props.entry.dn },
    client: app?.client,
  });
  if (!response.error) emit("reload-form", props.entry.dn, [props.attr.name!]);
}
</script>

<style scoped>
div.optional span.oc {
  @apply text-front/70;
}

div.illegal,
input.illegal {
  @apply line-through text-danger;
}

div.rdn span.oc,
input.structural {
  font-weight: bold;
}

.add-btn,
.remove-btn,
.fa-info-circle,
.fa-question-circle {
  @apply opacity-40 hover:opacity-70 text-base;
}

input.disabled,
input:disabled {
  @apply border-b-0;
}

input.auto {
  @apply text-primary;
}

div.rdn span.oc::after {
  content: " (rdn)";
  font-weight: 200;
}
</style>
