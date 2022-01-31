<template>
  <div id="tree-view">
    <ul id="tree" v-if="shown &amp;&amp; tree" class="list-unstyled">
      <li v-for="item in tree.visible()" :key="item.dn"
        :id="item.dn" :class="item.structuralObjectClass">
          <span v-for="i in (item.level - tree.level)" class="indent" :key="i"></span>
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

import NodeLabel from './NodeLabel.vue'


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

  visible: function() {
    if (!this.hasSubordinates || !this.open) return [this];
    return [this].concat(
      this.subordinates.flatMap(
        node => node.visible()));
  },
};


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

    shown: {
      type: Boolean,
      required: true,
    },

    schema: {
      type: Object,
      required: true,
    },
  },

  inject: [ 'xhr' ],

  data: function() {
    return {
      tree: undefined,
    }
  },

  created: async function() {
    await this.reload('base');
    this.$emit('base-dn', this.tree.dn);
  },

  watch: {

    active: async function(selected) {

      // Special case: Full tree reload
      if (selected == '-' || selected == 'base') {
        await this.reload('base');
        return;
      }

      // Reveal the selected DN in the tree
      // by opening all parent nodes
      const dn = new this.schema.DN(selected || this.tree.dn),
        parents = dn.parents(this.tree.dn);

      parents.reverse();
      for (let i=0; i < parents.length; ++i) {
        const p = parents[i].value, node = this.tree.find(p);
        if (!node.loaded) await this.reload(p);
        this.$set(node, 'open', true);
      }

      // Special case: Item was added, renamed or deleted
      if (!this.tree.find(dn.value)) {
        await this.reload(dn.parent.value);
        this.$set(this.tree.find(dn.parent.value), 'open', true);
      }
    },

  },
    
  methods: {

    clicked: async function(dn) {
      const item = this.tree.find(dn);
      if (item.hasSubordinates && !item.open) await this.toggle(item);
      this.$emit('select-dn', dn);
    },

    // Reload the subtree at entry with given DN
    reload: async function(dn) {
      const response = await this.xhr({ url: 'api/tree/' + dn }) || [];
      response.sort((a, b) => a.dn.toLowerCase().localeCompare(b.dn.toLowerCase()));

      if (dn == 'base') {
        this.tree = new Node(response[0]);
        await this.toggle(this.tree);
        return;
      }

      const item = this.tree.find(dn);
      this.$set(item, 'subordinates', response.map(node => new Node(node)));
      return response;
    },

    // Hide / show tree elements
    toggle: async function(item) {
      if (!item.open && !item.loaded) await this.reload(item.dn);
      this.$set(item, 'open', !item.open);
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
