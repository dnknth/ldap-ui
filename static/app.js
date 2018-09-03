"use strict";

var app = new Vue({
    
    // root <div> in page
    el: "#app",
    
    data: {
        // authentication
        user: null,             // logged in user
        
        // tree view
        tree: [],               // the tree that has been loaded so far
        treeMap: {},            // DN -> item mapping to check entry visibility
        icons: {                // OC -> icon mapping in tree
            inetOrgPerson:      'address-book',
            organization:       'globe',
            organizationalRole: 'robot',
            organizationalUnit: 'sitemap',
            groupOfNames:       'user-friends',
            groupOfUniqueNames: 'user-friends',
            posixGroup:         'user-friends',
            person:             'user-tie',
        },

        // alerts
        error: {},              // status alert
        
        // search
        searchResult: null,
        
        // entry editor
        newEntry: null,         // set by addDialog()
        copyDn: null,           // set by copy dialog
        
        entry: null,            // entry in editor
        attrMap: {              // input types for matching rules
            'integerMatch': 'number',
        },
        selectedOc: null,       // objectClass selection
        newAttr: null,          // auxillary attribute to add
        newRdn: null,           // new RDN for rename operation
        
        // schema
        schema: {               // LDAP schema info
            attributes:    [],
            objectClasses: [],
            structural:    [],  // Names of structural OC
        },
        oc: null,               // objectclass in side panel
        attr: null,             // attribute in side panel
        hiddenFields: ['desc', 'name', 'names',
            'no_user_mod', 'obsolete', 'oid',
            'usage', 'syntax', 'sup'],
    },
    
    created: function() { // Runs on page load
        
        // Get the DN of the current user
        $.get('api/whoami', function( response) {
            app.user = response;
        });
        
        // Populate the tree view
        this.reload( 'base');
        
        // Load the schema
        $.get('api/schema', function( response) {
            app.schema = response;
            app.schema.structural = [];
            for (let n in response.objectClasses) {
                const oc = response.objectClasses[n];
                if (oc.kind == 'structural') {
                    app.schema.structural.push( oc.name);
                }
            }
        });
    },
    
    methods: {
        
        // Reload the subtree at entry with given DN
        reload: function( dn) {
            const treesize = this.tree.length;
            let pos = this.tree.indexOf( this.treeMap[ dn]);
            return $.get('api/tree/' + dn, function( response) {
                if (pos >= 0) app.tree[pos].loaded = true;
                ++pos;
                
                while( pos < app.tree.length
                    && app.tree[pos].dn.indexOf( dn) != -1) {
                        delete app.treeMap[ app.tree[pos].dn];
                        app.tree.splice( pos, 1);
                }
                for (let i = 0; i < response.length; ++i) {
                    const item = response[i];
                    app.treeMap[ item.dn] = item;
                    app.tree.splice( pos++, 0, item);
                    item.level = item.dn.split(',').length;
                    // Extra step is needed for treesize == 0
                    item.level -= app.tree[0].dn.split(',').length;
                }
                if (treesize == 0) app.toggle( app.tree[0]);
            });
        },

        // Make a node visible in the tree, reloading as needed
        reveal: function( dn) {
            // Simple case: Tree node is already loaded.
            // Just open all ancestors
            if (this.treeMap[dn]) {
                for( let p = this.parent( dn); p; p = this.parent( p.dn)) {
                    p.open = p.hasSubordinates = true;
                }
                this.tree = this.tree.slice(); // force redraw
                return;
            }
            
            // build list of ancestors to reload
            let parts = dn.split( ','),
                parents = [];
                
            while (true) {
                parts.splice( 0, 1);
                const pdn = parts.join( ',');
                parents.push( pdn);
                if (this.treeMap[pdn]) break;
            }
            
            // Walk down the tree
            function visit() {
                if (!parents.length) {
                    app.tree = app.tree.slice(); // force redraw
                    return;
                }
                const pdn = parents.pop();
                app.reload( pdn).done( function() {
                    app.treeMap[pdn].open = true;
                    visit();
                });
            }
            visit();
        },
        
        // Get the tree item containing a given DN
        parent: function( dn) {
            return this.treeMap[ dn.slice( dn.indexOf(',') + 1)];
        },
        
        // Get the icon classes for a tree node
        icon: function( item) {
            return ' fa-' +
                (item ? this.icons[ item.structuralObjectClass] : 'atom' || 'question');
        },
        
        // Hide / show tree elements
        toggle: function( item) {
            item.open = !item.open;
            this.tree = this.tree.slice(); // force redraw
            if (!item.loaded) this.reload( item.dn);
        },
        
        // Populate the "New Entry" form
        addDialog: function() {
            this.newEntry = {
                parent: this.entry.meta.dn,
                name: null,
                rdn: null,
                objectClass: null,
            };
            this.$refs.newRef.show();
        },
        
        // Create a new entry in the main editor
        createEntry: function( evt) {
            this.entry = null;
            if (!this.newEntry || !this.newEntry.objectClass
                || !this.newEntry.rdn || !this.newEntry.name) {
                    evt.preventDefault();
                    return;
            }

            let oc = this.getOc( this.newEntry.objectClass);
            this.entry = {
                meta: {
                    dn: this.newEntry.rdn + '=' + this.newEntry.name + ',' + this.newEntry.parent,
                    aux: [],
                    required: [],
                },
                attrs: {
                    objectClass: [],
                },
            };
            
            this.entry.attrs[this.newEntry.rdn] = [this.newEntry.name];
            
            // Add required attributes and objectClass parents
            while (oc) {
                for (let i = 0; i < oc.must.length; ++i) {
                    let must = oc.must[i];
                    if (!this.entry.attrs[ must]) {
                        this.entry.attrs[ must] = ['']
                    }
                    if (this.entry.meta.required.indexOf( must) == -1) {
                        this.entry.meta.required.push( must);
                    }
                }
                this.entry.attrs.objectClass.push( oc.name);
                if (!oc.sup || !oc.sup.length) break;
                oc = this.getOc( oc.sup[0]);
            }
            this.entry.meta.aux = [];
        },
        
        // Bring up the 'rename' dialog
        renameDialog: function() {
            this.newRdn = null;
            this.$refs.renameRef.show();
        },
        
        // Change the RDN for an entry
        renameEntry: function( evt) {
            const dn = this.entry.meta.dn,
                dnparts = dn.split(',');
                
            if (!this.newRdn || this.newRdn == dn.split('=')[0]) {
                evt.preventDefault();
                return;
            }
            
            const rdnAttr = this.entry.attrs[this.newRdn];
            if (!rdnAttr || !rdnAttr[0]) {
                showWarning( 'Illegal value for: ' + this.newRdn)
                evt.preventDefault();
                return;
            }
            
            const rdn = this.newRdn + '=' + rdnAttr[0];
            $.get('api/rename/' + dn + '/' + rdn, function( response) {
                app.entry = response;
                const parent = app.parent( dn);
                if (parent) app.reload( parent.dn);
            })
            .fail( function( xhr, errorType, error) {
                app.showError( xhr.responseText);
            });
        },
        
        // Pop up the copy dialog
        copyDialog: function() {
            this.error = {};
            this.copyDn = this.entry.meta.dn;
            this.$refs.copyRef.show();
        },
        
        // Load copied entry into the editor
        copyEntry: function( evt) {

            if (!this.copyDn) {
                evt.preventDefault();
                return;
            }
            
            if (this.copyDn == this.entry.meta.dn) {
                this.copyDn = null;
                this.showWarning( 'Entry not copied');
                return;
            }
            
            const parts = this.copyDn.split(','),
                rdnpart = parts[0].split('='), 
                rdn = rdnpart[0];

            if (rdnpart.length != 2 || this.entry.meta.required.indexOf( rdn) == -1) {
                this.copyDn = null;
                this.showError( 'Invalid RDN: ' + parts[0]);
                return;
            }
            
            this.entry.attrs[rdn] = [rdnpart[1]];
            this.entry.meta.dn = this.copyDn;
            this.newEntry = { dn: this.copyDn }
            this.copyDn = null;
        },
        
        // Load an entry into the editing form
        loadEntry: function( dn, changed) {
            this.newEntry = null;
            this.searchResult = null;
            this.reveal( dn);
            $.get('api/entry/' + dn, function( response) {
                app.entry = response;
                app.entry.changed = changed || [];
                Vue.nextTick( function () {
                    $('input.disabled').prop( 'disabled', true);
                });
            });
        },
        
        // Submit the entry form via AJAX
        change: function( evt) {
            evt.preventDefault();
            this.entry.changed = [];
            this.error = {};
            const dn = this.entry.meta.dn;
            
            $.ajax({
                url:  'api/entry/' + dn,
                type: this.newEntry ? 'PUT' : 'POST',
                data: JSON.stringify( this.entry.attrs),
                contentType: 'application/json; charset=utf-8',
                dataType: 'json',
                success: function( data) {
                    if ( data && data.changed && data.changed.length) {
                        app.showInfo( '👍 Saved changes');
                    }
                    if (app.newEntry) {
                        app.reload( app.parent( dn).dn);
                    }
                    app.newEntry = null;
                    app.loadEntry( dn, data.changed);
                }})
            .fail( function( xhr, errorType, error) {
                app.showError( xhr.responseText);
            });
        },
        
        // Delete an entry
        remove: function() {
            const dn = this.entry.meta.dn;
            $.ajax({
                url:  'api/entry/' + dn,
                type: 'DELETE',
                success: function( result) {
                    app.showInfo( 'Deleted entry: ' + dn);
                    app.entry = null;
                    app.reload( app.parent( dn).dn);
                }
            })
            .fail( function( xhr, errorType, error) {
                app.showError( xhr.responseText);
            });
        },
        
        // Get a schema objectClass by name
        getOc: function( name) {
            return this.schema.objectClasses[name.toLowerCase()];
        },
        
        // Callback for OC selection popup
        addOc: function( evt) {
            this.entry.attrs.objectClass.push( this.selectedOc);
            const must = this.schema.objectClasses[
                    this.selectedOc.toLowerCase()].must;
            for (let i = 0; i < must.length; ++i) {
                let m = must[i];
                if (this.entry.meta.required.indexOf( m) == -1) {
                    this.entry.meta.required.push( m);
                }
                if (!this.entry.attrs[ m]) {
                    this.entry.attrs[ m] = [''];
                }
            }
            this.selectedOc = null;
        },
        
        // Get a schema attribute by name
        getAttr: function( name) {
            const n = name.toLowerCase(),
                  a = this.schema.attributes[n];
            if (a) return a;

            // brute-force search for alternative names
            for (att in this.schema.attributes) {
                const a2 = this.schema.attributes[att];
                for (let i = 0; i < a2.names.length; ++i) {
                    let name = a2.names[i];
                    if (name.toLowerCase() == n) return a2;
                }
            }
        },
        
        // Show popup for attribute selection
        attrDialog: function() {
            this.newAttr = null;
            this.$refs.attrRef.show();
        },
        
        // Add the selected attribute
        addAttr: function( evt) {
            if (!this.newAttr) {
                evt.preventDefault();
                return;
            }
            
            this.entry.attrs[this.newAttr] = [''];
            this.newAttr = null;
        },
                
        // Add an empty row in the entry form
        addRow: function( key, values) {
            if (key == 'objectClass') this.$refs.ocRef.show();
            else if (values.indexOf('') == -1) values.push('');
        },
        
        // Check for required fields by key
        required: function( key) {
            return this.entry.meta.required.indexOf( key) != -1;
        },
        
        // Has the key been updated on last entry modification? 
        changed: function( key) {
            return this.entry && this.entry.changed
                && this.entry.changed.indexOf( key) != -1;
        },
        
        // Guess the <input> type for an attribute
        fieldType: function( attr) {
            return attr == 'userPassword' ? 'password'
                : this.attrMap[ this.getAttr(attr).equality] || 'text';
        },
        
        // Is the given value a structural object class?
        isStructural: function( key, val) {
            return key == 'objectClass'
                && this.schema.structural.indexOf( val) != -1;
        },
        
        // Run a search against the directory
        search: function( evt) {
            evt.preventDefault();
            const q = $('input#q').val();
            
            $.get('api/search/' + q, function( response) {
                app.searchResult = null;
                app.error = {};
                if (!response || !response.length) {
                    app.showWarning( 'No search results');
                }
                else if (response.length == 1) {
                    // load single result for editing
                    app.entry = response[0];
                    app.reveal( app.entry.meta.dn);
                }
                else { // multiple results
                    app.entry = null;
                    app.searchResult = response;
                }
            });
        },

        // Display an info popup
        showInfo: function( msg) {
            this.error = { counter: 5, type: 'success', msg: '' + msg }
        },
        
        // Flash a warning popup
        showWarning: function( msg) {
            this.error = { counter: 10, type: 'warning', msg: '⚠️ ' + msg }
        },
        
        // Report an error
        showError: function( msg) {
            this.error = { counter: 60, type: 'danger', msg: '⛔ ' + msg }
        },
        
    },
    
    computed: {
        
        // All visible tree entries (with non-collaped parents)
        treeItems: function() {
            const p = this.parent;
            return this.tree.filter( function( item) {
                for (let i = p( item.dn); i; i = p( i.dn)) {
                    if (!i.open) return false;
                }
                return true;
            });
        },
        
        // Choice list of RDN attributes for a new entry
        rdn: function() {
            return !this.newEntry || !this.newEntry.objectClass ? []
                 : this.getOc( this.newEntry.objectClass).must.map( function( c) {
                     return app.getAttr( c).name;
            });
        },
        
        // Choice list for new attribute selection popup
        attrs: function() {
            if (!this.entry || !this.entry.attrs || !this.entry.attrs.objectClass) return [];
            
            let options = [];
            for (let i = 0; i < this.entry.attrs.objectClass.length; ++i) {
                const key = this.entry.attrs.objectClass[i],
                    may = this.getOc( key).may;
                for (let j = 0; j < may.length; ++j) {
                    let a = may[j];
                    if (options.indexOf( a) == -1 && !this.entry.attrs[a]) {
                        options.push( a);
                    }
                }
            }
            return options;
        },
    },
})
