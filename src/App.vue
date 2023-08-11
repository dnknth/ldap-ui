<template>
  <div id="app">
    <nav-bar v-model:treeOpen="treeOpen" :dn="activeDn"
      @show-modal="modal = $event;" @select-dn="activeDn = $event;" />

    <ldif-import-dialog v-model:modal="modal" @ok="activeDn = '-';" />

    <div class="flex container">
      <div class="space-y-4"><!-- left column -->
        <tree-view v-model:activeDn="activeDn" v-show="treeOpen" @base-dn="baseDn = $event;" />
        <object-class-card v-model="oc" />
        <attribute-card v-model="attr" />
      </div>
      
      <div class="flex-auto mt-4"><!-- main editing area -->
        <transition name="fade"><!-- Notifications -->
          <div v-if="error"
              class="rounded mx-4 mb-4 p-3 border border-front/70 text-back/70" :class="error.type">
            {{ error.msg }}
            <span class="float-right control" @click="error = undefined">✖</span>
          </div>
        </transition>
      
        <entry-editor v-model:activeDn="activeDn" />
      </div>
    </div>

    <div v-if="false"><!-- Not rendered, prevents color pruning -->
      <span class="text-accent bg-accent"></span>
      <span class="text-back bg-back"></span>
      <span class="text-danger bg-danger"></span>
      <span class="text-front bg-front"></span>
      <span class="text-primary bg-primary"></span>
      <span class="text-secondary bg-secondary"></span>
    </div>
  </div>
</template>

<script>
  import AttributeCard from './components/schema/AttributeCard.vue';
  import EntryEditor from './components/editor/EntryEditor.vue';
  import { LdapSchema } from './components/schema/schema.js';
  import LdifImportDialog from './components/LdifImportDialog.vue';
  import NavBar from './components/NavBar.vue';
  import ObjectClassCard from './components/schema/ObjectClassCard.vue';
  import { request } from './request.js';
  import TreeView from './components/TreeView.vue';

  export default {
    name: 'App',

    components: {
      AttributeCard,
      EntryEditor,
      LdifImportDialog,
      NavBar,
      ObjectClassCard,
      TreeView,
    },

    data: function() {
      return {

        // authentication
        user: undefined,        // logged in user
        baseDn: undefined,
        
        // components
        treeOpen: true,         // Is the tree visible?
        activeDn: undefined,    // currently active DN in the editor
        modal: null,            // modal popup

        // alerts
        error: undefined,       // status alert
        
        // schema
        schema: new LdapSchema({}),

        // Flash cards
        oc: undefined,          // objectClass info in side panel
        attr: undefined,        // attribute info in side panel
      };
    },

    provide: function () {
      return {
        app: this,
      };
    },

    mounted: async function() { // Runs on page load
      // Get the DN of the current user
      this.user = await this.xhr({ url: 'api/whoami'});

      // Load the schema
      this.schema = new LdapSchema(await this.xhr({ url: 'api/schema' }));
    },

    watch: {
      attr: function(a) { if (a) this.oc = undefined; },
      oc: function(o) { if (o) this.attr = undefined; },
    },

    methods: {
      xhr: function(options) {
        return request(options)
          .then(xhr => JSON.parse(xhr.response))
          .catch(xhr => this.showException(xhr.response || "Unknown error"));
      },
      
      // Display an info popup
      showInfo: function(msg) {
        this.error = { counter: 5, type: 'success', msg: '' + msg }
        setTimeout(() => { this.error = undefined; }, 5000);
      },
      
      // Flash a warning popup
      showWarning: function(msg) {
        this.error = { counter: 10, type: 'warning', msg: '⚠️ ' + msg }
        setTimeout(() => { this.error = undefined; }, 10000);
      },
      
      // Report an error
      showError: function(msg) {
        this.error = { counter: 60, type: 'danger', msg: '⛔ ' + msg }
        setTimeout(() => { this.error = undefined; }, 60000);
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
  .control {
    @apply opacity-70 hover:opacity-90 cursor-pointer select-none leading-none pt-1 pr-1;
  }

  button, .btn, [type="button"] {
    @apply border-none px-3 py-2 rounded text-back dark:text-front;
  }

  .glyph {
    font-family: sans-serif, FontAwesome;
    font-style: normal;
  }

  .success {
    @apply bg-emerald-300;
  }

  .danger {
    @apply bg-red-300;
  }

  .warning {
    @apply bg-amber-200;
  }

  .fade-enter-active, .fade-leave-active {
    transition: opacity 0.5s ease;
  }

  .fade-enter-from, .fade-leave-to {
    opacity: 0;
  }
</style>
