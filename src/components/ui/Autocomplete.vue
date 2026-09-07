<template>
  <popover :open="show" @update:open="clear">
    <li
      v-for="item in results"
      :key="keyOf(item)"
      :title="titleOf(item)"
      role="menuitem"
      @click="pick(item)"
    >
      {{ labelOf(item) }}
    </li>
  </popover>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import Popover from "./Popover.vue";
import { state } from "@/state";

/**
 * Field names index into heterogeneous result objects (SearchResult has
 * {dn, name}, Attribute has {oid, ...}). Configure which field drives
 * display/`<li :key>`/title and which value to emit on selection.
 */
type Item = Record<string, unknown>;

const props = defineProps<{
    query?: string;
    for?: string; // input id to refocus after a pick
    search: (q: string) => Item[] | Promise<Item[]>;
    label?: string; // = "name" display + sort field
    keyLabel?: string; // = label, `<li :key>`
    titleLabel?: string; // tooltip; "dn" abbreviates via state.baseDn
    pickKey?: string; // = label, field value emitted as the pick
    autoPickSingle?: boolean; // auto-pick the single result (like DN search)
    exactMatchHides?: boolean; // hide a single result that equals the query
    warnEmpty?: boolean; // warn when a query yields no results
  }>(),
  results = ref<Item[]>([]),
  // Only auto-pick/resmall-warning quietly when there are >1 candidates; a
  // lone result is either picked (autoPickSingle) or kept displayed.
  show = computed(() => {
    const q = (props.query ?? "").trim();
    if (q == "" || results.value.length == 0) return false;
    if (
      props.exactMatchHides &&
      results.value.length == 1 &&
      propOf(results.value[0], props.pickKey ?? props.label ?? "name") == q
    )
      return false;
    if (props.autoPickSingle && results.value.length == 1) return false;
    return true;
  }),
  emit = defineEmits<{ pick: [value: string] }>();

function propOf(item: Item, field: string): string {
  return String(item[field] ?? "");
}

function keyLabel(): string {
  return props.keyLabel ?? props.label ?? "name";
}

function labelOf(item: Item): string {
  return propOf(item, props.label ?? "name");
}

function keyOf(item: Item): string {
  return propOf(item, keyLabel());
}

function titleOf(item: Item): string {
  if (props.titleLabel) return propOf(item, props.titleLabel);
  if ((props.label ?? "name") == "dn" || typeof item.dn != "string") return "";
  return state.baseDn && item.dn != state.baseDn
    ? item.dn.replace(state.baseDn, "…")
    : item.dn;
}

watch(
  () => props.query,
  async (q) => {
    if (!q) {
      clear();
      return;
    }
    const found = (await props.search(q)) ?? [];
    const field = props.label ?? "name";
    found.sort((a: Item, b: Item) =>
      propOf(a, field).toLowerCase().localeCompare(propOf(b, field).toLowerCase()),
    );
    results.value = found;

    if (found.length == 0 && props.warnEmpty) {
      state.showWarning("No search results");
      return;
    }
    if (props.autoPickSingle && found.length == 1) {
      pick(found[0]!);
    }
  },
);

function clear() {
  results.value = [];
}

// use an auto-completion choice
function pick(item: Item) {
  emit("pick", propOf(item, props.pickKey ?? props.label ?? "name"));
  clear();

  nextTick(() => {
    // Return focus to the search input
    if (props.for) {
      const el = document.getElementById(props.for);
      if (el) el.focus();
    }
  });
}
</script>