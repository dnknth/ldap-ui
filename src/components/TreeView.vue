<template>
  <div class="rounded-md bg-front/[.07] p-4 shadow-md shadow-front/20">
    <ul v-if="tree" class="list-unstyled">
      <li v-for="item in tree.visible()" :key="item.dn"
        :id="item.dn" :class="item.structuralObjectClass">
          <span v-for="i in (item.level - tree.level)" class="ml-6" :key="i"></span>
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

<script setup>
  import { inject, onMounted, ref, watch } from 'vue';
  import NodeLabel from './NodeLabel.vue';

  function Node(json) {
    Object.assign(this, json);
    this.level = this.dn.split(',').length;
    if (this.hasSubordinates) {
      this.subordinates = [];
      this.open = false;
    }
  }

  Node.prototype = {
    find: function(dn) {
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
    },

    get loaded() {
      return !this.hasSubordinates || this.subordinates.length > 0;
    },
    
    parentDns: function(baseDn) {
      const dns = [];
        for (let dn = this.dn;;) {
          dns.push(dn);
          const idx = dn.indexOf(',');
          if (idx == -1 || dn == baseDn) break;
          dn = dn.subString(idx + 1);
        }
        return dns;
    },

    visible: function() {
      if (!this.hasSubordinates || !this.open) return [this];
      return [this].concat(
        this.subordinates.flatMap(
          node => node.visible()));
    },
  };

  const props = defineProps({
      activeDn: String,
    }),
    app = inject('app'),
    tree = ref(null),
    emit = defineEmits(['base-dn', 'update:activeDn']);

  onMounted(async () => {
    await reload('base');
    emit('base-dn', tree.value.dn);
  });

  watch(() => props.activeDn, async (selected) => {
    if (!selected) return;
    
    // Special case: Full tree reload
    if (selected == '-' || selected == 'base') {
      await reload('base');
      return;
    }
    
    // Get all parents of the selected entry in the tree
    const dn = new app.schema.DN(selected || tree.value.dn);
    let hierarchy = [];
    for (let node = dn; node; node = node.parent) {
      hierarchy.push(node);
      if (node == tree.value.dn) break;
    }

    // Reveal the selected entry by opening all parents
    hierarchy.reverse();
    for (let i = 0; i < hierarchy.length; ++i) {
      const p = hierarchy[i].toString(),
        node = tree.value.find(p);
      if (!node) break;
      if (!node.loaded) await reload(p);
      node.open = true;
    }

    // Reload parent if entry was added, renamed or deleted
    if (!tree.value.find(dn.toString())) {
      await reload(dn.parent.toString());
      tree.value.find(dn.parent.toString()).open = true;
    }
  });
      
  async function clicked(dn) {
    const item = tree.value.find(dn);
    if (item.hasSubordinates && !item.open) await toggle(item);
    emit('update:activeDn', dn);
  }

      // Reload the subtree at entry with given DN
  async function reload(dn) {
    const response = await app.xhr({ url: 'api/tree/' + dn }) || [];
    response.sort((a, b) => a.dn.toLowerCase().localeCompare(b.dn.toLowerCase()));

    if (dn == 'base') {
      tree.value = new Node(response[0]);
      await toggle(tree.value);
      return;
    }

    const item = tree.value.find(dn);
    item.subordinates = response.map(node => new Node(node));
    item.hasSubordinates = item.subordinates.length > 0;
    return response;
  }

  // Hide / show tree elements
  async function toggle(item) {
    if (!item.open && !item.loaded) await reload(item.dn);
    item.open = !item.open;
  }
</script>

<style scoped>
  .active {
    @apply text-front font-bold;
  }
</style>
