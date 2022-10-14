<template>
  <span @click="$emit('select-dn', dn)" class="node-label" :class="cssClass" :title="dn">
    <i class="fa" :class="icon" v-if="oc"></i>
    <slot>{{ label }}</slot>
  </span>
</template>

<script>
export default {

  name: 'NodeLabel',

  props: {
    dn: String,
    cssClass: {
      type: String,
      default: '',
    },
    oc: {
      type: String,
      required: true,
    },
  },

  data: function() {
    return {
      icons: {               // OC -> icon mapping in tree
        account:            'user',
        groupOfNames:       'users',
        groupOfURLs:        'users',
        groupOfUniqueNames: 'users',
        inetOrgPerson:      'address-book',
        krbContainer:       'lock',
        krbPrincipal:       'user-o',
        krbRealmContainer:  'globe',
        organization:       'globe',
        organizationalRole: 'android',
        organizationalUnit: 'sitemap',
        person:             'user',
        posixGroup:         'users',
      }
    }
  },

  computed: {

    icon: function() { // Get the icon classes for a tree node
      return ' fa-' + this.icons[this.oc] || 'question';
    },

    // Shorten a DN for readability
    label: function() {
      return (this.dn || '').split(',')[0]
        .replace(/^cn=/, '')
        .replace(/^krbPrincipalName=/, '');
    },
  },
}
</script>

<style scoped>
  i.fa {
    margin-right: 0.3em;
  }

  .node-label:hover {
    color: var(--active);
  }
</style>
