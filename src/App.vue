<template>
  <div id="app">

    <nav-bar v-model="treeOpen" :dn="activeDn" :base-dn="baseDn" :user="user"
      :showWarning="showWarning" :schema="schema"
      @select-dn="activeDn = $event" @display-oc="displayOc" />

    <ldif-import-dialog @select-dn="activeDn = $event" />

    <b-container fluid>
      <b-row>
        <b-col cols="*" id="left">
          <tree-view v-model="activeDn" :shown="treeOpen" :schema="schema"
            @base-dn="baseDn = $event" />
          <object-class-card :oc="oc" @display-oc="displayOc" @display-attr="displayAttr" />
          <attribute-card v-if="attr" :attr="attr" @display-attr="displayAttr" />
        </b-col>
        
        <b-col id="main">
          <b-alert dismissible fade :variant="error.type"
              :show="error &amp;&amp; error.counter" @dismissed="error.counter=0">
            {{ error.msg }}
          </b-alert>
          
          <editor v-model="activeDn" :showInfo="showInfo"
            :schema="schema" :user="user" :base-dn="baseDn"
            @display-attr="displayAttr" @display-oc="displayOc" />

        </b-col>
      </b-row>
    </b-container>
  </div>
</template>

<script>

import AttributeCard from './components/schema/AttributeCard.vue'
import Editor from './components/editor/Editor.vue'
import { LdapSchema } from './components/schema/schema.js'
import LdifImportDialog from './components/LdifImportDialog.vue'
import NavBar from './components/NavBar.vue'
import ObjectClassCard from './components/schema/ObjectClassCard.vue'
import { request } from './request.js'
import TreeView from './components/TreeView.vue'


export default {

  name: 'App',

  components: {
    AttributeCard,
    Editor,
    LdifImportDialog,
    NavBar,
    ObjectClassCard,
    TreeView,
  },

  data: function() {
    return {

      // authentication
      user: null,             // logged in user
      baseDn: undefined,
      
      treeOpen: true,         // Is the tree visible?
      activeDn: undefined,    // currently active DN in the editor

      // alerts
      error: {},              // status alert
      
      // schema
      schema: new LdapSchema({}),

      // Flash cards
      oc: null,               // objectClass info in side panel
      attr: null,             // attribute info in side panel
    }
  },

  provide: function () {
    return { xhr: this.xhr, }
  },

  mounted: async function() { // Runs on page load

    // Get the DN of the current user
    this.user = await this.xhr({ url: 'api/whoami'});

    // Load the schema
    this.schema = new LdapSchema(await this.xhr({ url: 'api/schema' }));

    document.getElementById('search').focus();
  },

  methods: {
    
    xhr: function(options) {
      return request(options)
        .then(xhr => JSON.parse(xhr.response))
        .catch(xhr => this.showException(xhr.response || "Unknown error"));
    },
    
    displayOc: function(name) {
      this.attr = undefined;
      this.oc = name ? this.schema.oc(name) : undefined;
    },
    
    displayAttr: function(name) {
      this.attr = name ? this.schema.attr(name) : undefined;
      this.oc = undefined;
    },
     
    // Display an info popup
    showInfo: function(msg) {
      this.error = { counter: 5, type: 'success', msg: '' + msg }
    },
    
    // Flash a warning popup
    showWarning: function(msg) {
      this.error = { counter: 10, type: 'warning', msg: '⚠️ ' + msg }
    },
    
    // Report an error
    showError: function(msg) {
      this.error = { counter: 60, type: 'danger', msg: '⛔ ' + msg }
    },

    showException: function(msg) {
      const span = document.createElement('span');
      span.innerHTML = msg.replace("\n", " ");
      const titles = span.getElementsByTagName('title');
      for (let i = 0; i < titles.length; ++i) {
        span.removeChild(titles[i]);
      }
      let text = '';
      const headlines = span.getElementsByTagName('h1');
      for (let i = 0; i < headlines.length; ++i) {
        text = text + headlines[i].textContent + ': ';
        span.removeChild(headlines[i]);
      }
      this.showError(text + ' ' + span.textContent);
    },
  },
}
</script>

<style>
  :root {
    --body-fg: #222;
    --body-bg: white;
    --muted-fg: #333;
    --muted-bg: #EEE;
    --accent: var(--cyan);
    --active: black;
    --border: rgb(0,0,0,.125);
    --input-bg: white;
    --modal-border: rgba(0,0,0,.2);
    --modal-divider: #dee2e6;
    --tree-icon: DarkGray;
    --tree-bg: var(--body-bg);
    --tree-shadow: rgba(0,0,0,0.5);
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --body-fg: #EEE;
      --body-bg: #111;
      --muted-fg: #CCC;
      --muted-bg: #222;
      --active: white;
      --border: #333;
      --input-bg: #444;
      --modal-border: #666;
      --modal-divider: #444;
      --tree-icon: LightGray;
      --tree-bg: var(--muted-bg);
      --tree-shadow: rgba(128,128,128,0.5);
    }

    select.custom-select {
      background: var(--input-bg) url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' width='4' height='5' viewBox='0 0 4 5'%3e%3cpath fill='%23CCC' d='M2 0L0 2h4zm0 5L0 3h4z'/%3e%3c/svg%3e") right .75rem center/8px 10px no-repeat;
    }
  }

  body {
    color: var(--body-fg);
    background-color: var(--body-bg);
  }

  div.card {
    margin-bottom: 1em;
    background-color: var(--muted-bg);
    color: var(--body-fg);
    border: 1px solid var(--border);
  }

  .card div.card-header {
    color: var(--muted-fg);
  }

  div.card-body {
    background-color: var(--body-bg);
  }

  a, a:hover {
    text-decoration: none;
    color: var(--active);
  }

  .u {
    text-decoration: underline;
  }

  .right {
    float: right;
    margin-left: 0.3em;
  }

  .red {
    color: red !important;
  }

  .green {
    color: green !important;
  }

  .clickable {
    cursor: pointer;
  }

  .close {
    color: var(--body-fg);
    text-shadow: 0 1px 0 var(--body-bg);
  }

  .control {
    opacity: 0.4;
    cursor: pointer;
  }

  .control:hover {
    opacity: 0.75;
  }

  .close-box {
    font-size: 150%;
    position: absolute;
    top: 0.2em;
    right: 16px;
  }

  span.header, p.strong {
    font-weight: bold;
  }

  #main {
    margin-top: 1em;
  }

  .hidden {
    display: none;
  }

  input.form-control, textarea.form-control, select.custom-select {
    color: var(--body-fg) !important;
    background-color: var(--input-bg) !important;
  }

  .modal-header, .modal-footer {
    border-color: var(--modal-divider);
  }

  .modal-content {
    border-color: var(--modal-border);
    background-color: var(--body-bg);
  }

  .dropdown-menu {
    border: 1px solid var(--modal-border);
    background-color: var(--muted-bg);
  }

  .dropdown-item {
    color: var(--body-fg);
  }

  .glyph {
    font-family: sans-serif, FontAwesome;
  }

</style>
