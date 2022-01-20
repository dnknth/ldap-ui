<template>
  <div id="tree-view">
    <ul id="tree" v-if="shown" class="list-unstyled">
      <li v-for="item in treeItems" :key="item.dn"
        :id="item.dn" :class="item.structuralObjectClass">
          <span v-for="i in item.level" class="indent" :key="i"></span>
          <span v-if="item.hasSubordinates" class="clickable opener"
            @click="toggle(item)"><i :class="'fa fa-chevron-circle-'
              + (item.open ? 'down' : 'right')"></i></span>
          <span v-else class="indent"></span>
          <node-label :dn="item.dn" :oc="item.structuralObjectClass"
            cssClass="clickable tree-link"
            @select-dn="clicked" :class="{ active : active == item.dn }">
            <span v-if="!item.level">
              {{ item.dn }}
            </span>
          </node-label>
      </li>
    </ul>
  </div>
</template>

<script>

import { DN } from './schema/DN.js'
import NodeLabel from './NodeLabel.vue'

export default {

  name: 'TreeView',

  components: {
    NodeLabel,
  },

  model: {
    prop: 'active',
    event: 'select-dn'
  },

  props: {
    active: String,
    shown: Boolean,
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      tree: [],              // the tree that has been loaded so far
      treeMap: {},           // DN -> item mapping to check entry visibility
    }
  },

  created: function() {
    this.reload('base');
  },

  watch: {

    active: async function(selected) {
      const base = this.tree[0].dn,
        dn = new DN(selected || base),
        parents = dn.parents(this.tree[0].dn);
      parents.reverse();
      for (let i=0; i < parents.length; ++i) {
        const p = parents[i].value, node = this.treeMap[p]; 
        if (!node || !node.open) {
          await this.reload(p);
        }
        this.treeMap[p].open = true;
      }

      // Special case: Full tree reload
      if (dn == '-') {
        await this.reload(base);
        this.treeMap[base].open = true;
      }

      // Special case: Item was added, renamed or deleted
      else if (dn != 'base' && !this.treeMap[dn.value]) {
        const pdn = dn.parent.value;
        await this.reload(pdn);
        this.treeMap[pdn].open = true;
      }
      this.redraw();
    },

  },
    
  methods: {

    clicked: function(dn) {
      const item = this.treeMap[dn];
      if (item.hasSubordinates && !item.open) {
        this.reload(item.dn);
        item.open = true;
        this.redraw();
      }
      this.$emit('select-dn', dn);
    },

    // Reload the subtree at entry with given DN
    reload: async function(dn) {
      const treesize = this.tree.length;
      let pos = this.tree.indexOf(this.treeMap[dn]) + 1;
      while (pos < this.tree.length && this.tree[pos].dn.includes(dn)) {
        delete this.treeMap[this.tree[pos].dn];
        this.tree.splice(pos, 1);
      }

      const response = await this.xhr({ url: 'api/tree/' + dn }) || [];
      response.sort((a, b) => a.dn.toLowerCase().localeCompare(b.dn.toLowerCase()));

      for (let i=0; i < response.length; ++i) {
        const item = response[i];
        this.treeMap[item.dn] = item;
        this.tree.splice(pos++, 0, item);
        item.level = item.dn.split(',').length - this.tree[0].dn.split(',').length;
      }

      if(treesize == 0) this.toggle(this.tree[0]);
      return response;
    },

    redraw: function() {
      this.tree = this.tree.slice();
    },

    // Hide / show tree elements
    toggle: function(item) {
      item.open = !item.open;
      if (item.open) this.reload(item.dn);
      this.redraw();
    },
    
  },

  computed: {
      
    // All visible tree entries (with expanded parents)
    treeItems: function() {
      const tm = this.treeMap;
      return this.tree.filter(item =>
        new DN(item.dn).parents()
          .filter(p => tm[p.value])
          .every(p => tm[p.value].open));
    },

  },
}
</script>

<style scoped>
  #tree-view {
    box-shadow: 4px 4px 5px 0 var(--tree-shadow);
    background-color: var(--tree-bg);
  }

  ul#tree {
    margin: 0 1em 1em 1em;
    padding: 1em 0;
  }

  ul#tree li {
    margin-top: 0.1em;
    white-space: nowrap;
  }

  .tree-link i.fa {
    color: var(--tree-icon);
  }

  span.active {
    font-weight: bold;
  }

  span.indent {
    margin-left: 1.2em;
  }

  span.opener {
    opacity: 0.4;
    margin-right: 0.3em;
  }

  span.opener:hover {
    opacity: 0.7;
  }

</style>
