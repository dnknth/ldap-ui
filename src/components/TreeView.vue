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

<script>
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

    props: {
      activeDn: String,
    },

    inject: [ 'app' ],

    data: function() {
      return {
        tree: undefined,
      };
    },

    created: async function() {
      await this.reload('base');
      this.$emit('base-dn', this.tree.dn);
    },

    watch: {
      activeDn: async function(selected) {
        // Special case: Full tree reload
        if (selected == '-' || selected == 'base') {
          await this.reload('base');
          return;
        }

        // Reveal the selected DN in the tree
        // by opening all parent nodes
        const dn = new this.app.schema.DN(selected || this.tree.dn),
          parents = dn.parents(this.tree.dn);

        parents.reverse();
        for (let i=0; i < parents.length; ++i) {
          const p = parents[i].value, node = this.tree.find(p);
          if (!node.loaded) await this.reload(p);
          node.open = true;
        }

        // Special case: Item was added, renamed or deleted
        if (!this.tree.find(dn.value)) {
          await this.reload(dn.parent.value);
          this.tree.find(dn.parent.value).open = true;
        }
      },

    },
      
    methods: {
      clicked: async function(dn) {
        const item = this.tree.find(dn);
        if (item.hasSubordinates && !item.open) await this.toggle(item);
        this.$emit('update:activeDn', dn);
      },

      // Reload the subtree at entry with given DN
      reload: async function(dn) {
        const response = await this.app.xhr({ url: 'api/tree/' + dn }) || [];
        response.sort((a, b) => a.dn.toLowerCase().localeCompare(b.dn.toLowerCase()));

        if (dn == 'base') {
          this.tree = new Node(response[0]);
          await this.toggle(this.tree);
          return;
        }

        const item = this.tree.find(dn);
        item.subordinates = response.map(node => new Node(node));
        item.hasSubordinates = item.subordinates.length > 0;
        return response;
      },

      // Hide / show tree elements
      toggle: async function(item) {
        if (!item.open && !item.loaded) await this.reload(item.dn);
        item.open = !item.open;
      },
      
    },
  }
</script>

<style scoped>
  .active {
    @apply text-front font-bold;
  }
</style>
