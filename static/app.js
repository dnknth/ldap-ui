// Shallow-copy an object
function Clone( obj) {
    if (null !== obj) {
        for (let attr in obj) {
            if (obj.hasOwnProperty(attr)) {
                this[attr] = obj[attr];
            }
        }
    }
}


window.app = new Vue({
    
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
            person:             'user',
        },

        // alerts
        error: {},              // status alert
        
        // search
        searchResult: null,
        
        // entry editor
        newEntry: null,         // set by addDialog()
        copyDn: null,           // set by copy dialog
        
        entry: null,            // entry in editor
        attrMap: {
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
            'no_user_mod', 'obsolete', 'oid', 'usage', 'syntax', 'sup'],
    },
    
    created: function() { // Runs on page load
        
        // Get the DN of the current user
        $.get('api/whoami', function( response) {
            window.app.user = response;
        });
        
        // Populate the tree view
        this.reload( 'base');
        
        // Load the schema
        $.get('api/schema', function( response) {
            window.app.schema = response;
            window.app.schema.structural = [];
            for (i in window.app.schema.objectClasses) {
                const oc = window.app.schema.objectClasses[i];
                if (oc.kind == 'structural') {
                    window.app.schema.structural.push( oc.name);
                }
            }
        });
    },
    
    methods: {
        
        // Reload the subtree at entry with given DN
        reload: function( dn) {
            let pos = Math.max( this.tree.indexOf( this.treeMap[ dn]), 0);
            $.get('api/tree/' + dn, function( response) {
                while( pos < window.app.tree.length
                    && window.app.tree[pos].dn.indexOf( dn) != -1) {
                        delete window.app.treeMap[ window.app.tree[pos].dn];
                        window.app.tree.splice( pos, 1);
                }
                response[0].loaded = true;
                for (item of response) {
                    window.app.treeMap[ item.dn] = item;
                    window.app.tree.splice( pos++, 0, item);
                    item.collapsed = !item.loaded;
                    item.level = item.dn.split(',').length;
                    // Extra step is needed if this === tree[0]
                    item.level -= window.app.tree[0].dn.split(',').length;
                }
            });
        },

        // Get the tree item containing a given DN
        parent: function( dn) {
            const comma = dn.indexOf(',');
            return this.treeMap[ dn.slice( comma + 1)];
        },
        
        // Hide / show tree elements
        toggle: function( item) {
            item.collapsed = !item.collapsed;
            this.tree = this.tree.slice();
            if (!item.collapsed && !item.loaded) {
                this.reload( item.dn);
            }
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
                    structuralObjectClass: [this.newEntry.objectClass],
                },
            };
            
            this.entry.attrs[this.newEntry.rdn] = [this.newEntry.name];
            
            // Add required attributes and objectClass parents
            while (oc) {
                for (let must of oc.must) {
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
        
        renameDialog: function() {
            this.newRdn = null;
            this.$refs.renameRef.show();
        },
        
        renameEntry: function( evt) {
            const dn = this.entry.meta.dn,
                dnparts = dn.split(',');
                
            if (!this.newRdn || this.newRdn == dnparts[0].split('=')[0]) {
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
                window.app.entry = response;
                window.app.reload( window.app.parent( dn).dn);
            })
            .fail( function( xhr, errorType, error) {
                window.app.showError( xhr.responseText);
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
            $.get('api/entry/' + dn, function( response) {
                window.app.entry = response;
                window.app.entry.changed = changed ? changed : [];
            });
        },
        
        // Reload the edit form contents from directory
        reset: function() {
            this.loadEntry( this.entry.meta.dn);
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
                        window.app.showInfo( '👍 Saved changes');
                    }
                    if (window.app.newEntry) {
                        window.app.reload( window.app.parent( dn).dn);
                    }
                    window.app.newEntry = null;
                    window.app.loadEntry( dn, data.changed);
                }})
            .fail( function( xhr, errorType, error) {
                window.app.showError( xhr.responseText);
            });
        },
        
        // Delete an entry
        remove: function() {
            const dn = this.entry.meta.dn;
            $.ajax({
                url:  'api/entry/' + dn,
                type: 'DELETE',
                success: function( result) {
                    window.app.showInfo( 'Entry deleted');
                    window.app.entry = null;
                    window.app.reload( window.app.parent( dn).dn);
                }
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
            for (let m of must) {
                if (this.entry.meta.required.indexOf( m) == -1) {
                    this.entry.meta.required.push( m);
                }
                if (!this.entry.attrs[ m]) {
                    this.entry.attrs[ m] = [''];
                }
            }
            this.entry = new Clone( this.entry);
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
                for (let name of a2.names) {
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
            else if (values.indexOf('') == -1) {
                values.push('');
                this.entry = new Clone( this.entry);
            }
        },
        
        // Check for required fields by key
        required: function( key) {
            return this.entry.meta.required.indexOf( key) != -1;
        },
        
        // Has the key been updated on last entry modification? 
        changed: function( key) {
            if (!this.entry || !this.entry.changed) return false;
            return this.entry.changed.indexOf( key) != -1;
        },
        
        // Guess the <input> type for an attribute
        fieldType: function( attr) {
            if (attr == 'userPassword') return 'password';
            return this.attrMap[ this.getAttr(attr).equality] || 'text';
        },
        
        // Is the given value a structural object class?
        isStructural: function( key, val) {
            return key == 'objectClass'
                && val == this.entry.attrs.structuralObjectClass[0];
        },
        
        // Run a search against the directory
        search: function( evt) {
            evt.preventDefault();
            const q = $('input#q').val();
            
            $.get('api/search/' + q, function( response) {
                window.app.searchResult = null;
                window.app.error = {};
                if (!response || !response.length) {
                    window.app.showWarning( 'No search results');
                }
                else if (response.length == 1) {
                    // load single result for editing
                    window.app.entry = response[0];
                }
                else { // multiple results
                    window.app.entry = null;
                    window.app.searchResult = response;
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
                    if (i.collapsed) return false;
                }
                return true;
            });
        },
        
        // Choice list of RDN attributes for a new entry
        rdn: function() {
            if (!this.newEntry || !this.newEntry.objectClass) return [];
            
            return this.getOc( this.newEntry.objectClass).must.map(
                c => this.getAttr( c).name);
        },
        
        // Choice list for new attribute selection popup
        attrs: function() {
            if (!this.entry || !this.entry.attrs || !this.entry.attrs.objectClass) return [];
            
            let options = [];
            for (let key of this.entry.attrs.objectClass) {
                for (let a of this.getOc( key).may) {
                    if (options.indexOf( a) == -1 && !this.entry.attrs[a]) {
                        options.push( a);
                    }
                }
            }
            return options;
        },
    },
})
