<template>
  <div class="rounded-md bg-front/[.07] p-4 shadow-md shadow-front/20">
    <ul v-if="tree" class="list-unstyled">
      <li v-for="item in tree.visible()" :key="item.dn"
        :id="item.dn" :class="item.structuralObjectClass">
          <span v-for="i in (item.level! - tree.level!)" class="ml-6" :key="i"></span>
          <span v-if="item.hasSubordinates" class="control"
            @click="toggle(item)"><i :class="'control p-0 fa fa-chevron-circle-'
              + (item.open ? 'down' : 'right')"></i></span>
          <span v-else class="mr-4"></span>

          <node-label :dn="item.dn" :oc="item.structuralObjectClass"
            class="tree-link whitespace-nowrap text-front/80"
            @select-dn="clicked" :class="{ active : activeDn == item.dn }">
              <span v-if="!item.level">{{ item.dn }}</span>
          </node-label>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
  import { DN } from './schema/schema';
  import { inject, onMounted, ref, watch } from 'vue';
  import NodeLabel from './NodeLabel.vue';
  import type { Provided } from './Provided';
  import type { TreeNode } from './TreeNode';

  class Node implements TreeNode {
    dn: string;
    level: number | undefined;
    hasSubordinates: boolean;
    structuralObjectClass: string;
    open: boolean = false;
    subordinates: Node[] = [];

    constructor(json: TreeNode) {
      this.dn = json.dn;
      this.level = this.dn.split(',').length;
      this.hasSubordinates = json.hasSubordinates;
      this.structuralObjectClass = json.structuralObjectClass;
      if (this.hasSubordinates) {
        this.subordinates = [];
        this.open = false;
      }
    }

    find(dn: string): Node | undefined {
      // Primitive recursive search for a DN.
      // Compares DNs a strings, without any regard for 
      // distinguishedNameMatch rules.
      // See: https://ldapwiki.com/wiki/DistinguishedNameMatch

      if (this.dn == dn) return this;
      const suffix = ',' + this.dn;
      if (!dn.endsWith(suffix) || !this.hasSubordinates) return undefined;
      return this.subordinates
        .map(node => node.find(dn))
        .filter(node => node)[0];
    }

    get loaded(): boolean {
      return !this.hasSubordinates || this.subordinates.length > 0;
    }
    
    parentDns(baseDn: string): string[] {
      const dns = [];
        for (let dn = this.dn;;) {
          dns.push(dn);
          const idx = dn.indexOf(',');
          if (idx == -1 || dn == baseDn) break;
          dn = dn.substring(idx + 1);
        }
        return dns;
    }

    visible(): Node[] {
      if (!this.hasSubordinates || !this.open) return [this];
      return [this as Node].concat(
        this.subordinates.flatMap(
          node => node.visible()));
    }
  }

  const props = defineProps({
      activeDn: String,
    }),
    app = inject<Provided>('app'),
    tree = ref<Node>(),
    emit = defineEmits(['base-dn', 'update:activeDn']);

  onMounted(async () => {
    await reload('base');
    emit('base-dn', tree.value?.dn);
  });

  watch(() => props.activeDn, async (selected) => {
    if (!selected) return;
    
    // Special case: Full tree reload
    if (selected == '-' || selected == 'base') {
      await reload('base');
      return;
    }
    
    // Get all parents of the selected entry in the tree
    const dn = new DN(selected || tree.value!.dn);
    const hierarchy = [];
    for (let node: DN | undefined = dn; node; node = node.parent) {
      hierarchy.push(node);
      if (node.toString() == tree.value?.dn) break;
    }

    // Reveal the selected entry by opening all parents
    hierarchy.reverse();
    for (let i = 0; i < hierarchy.length; ++i) {
      const p = hierarchy[i].toString(),
        node = tree.value?.find(p);
      if (!node) break;
      if (!node.loaded) await reload(p);
      node.open = true;
    }

    // Reload parent if entry was added, renamed or deleted
    if (!tree.value?.find(dn.toString())) {
      await reload(dn.parent!.toString());
      tree.value!.find(dn.parent!.toString())!.open = true;
    }
  });
      
  async function clicked(dn: string) {
    const item = tree.value?.find(dn);
    if (item && item.hasSubordinates && !item.open) await toggle(item);
    emit('update:activeDn', dn);
  }

      // Reload the subtree at entry with given DN
  async function reload(dn: string) {
    const response = await app?.xhr({ url: 'api/tree/' + dn }) as Node[] || [];
    response.sort((a: Node, b: Node) => a.dn.toLowerCase().localeCompare(b.dn.toLowerCase()));

    if (dn == 'base') {
      tree.value = new Node(response[0]);
      await toggle(tree.value);
      return;
    }

    const item = tree.value?.find(dn);
    if (item) {
      item.subordinates = response.map(node => new Node(node));
      item.hasSubordinates = item.subordinates.length > 0;
    }
    return response;
  }

  // Hide / show tree elements
  async function toggle(item: Node) {
    if (!item.open && !item.loaded) await reload(item.dn);
    item.open = !item.open;
  }
</script>

<style scoped>
  .active {
    @apply text-front font-bold;
  }
</style>
