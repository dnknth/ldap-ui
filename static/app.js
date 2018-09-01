window.app = new Vue({
    
    // root <div> in page
    el: "#app",
    
    data: {
        // authentication
        user: null,             // logged in user
        
        // tree view
        tree: [],               // complete tree
        icons: {                // OC -> icon mapping in tree
            inetOrgPerson:      'address-book',
            organization:       'globe',
            organizationalRole: 'robot',
            organizationalUnit: 'sitemap',
            groupOfNames:       'user-friends',
            person:             'user',
        },

        // alerts
        error: {},              // status alert
        
        // search
        searchResult: null,
        
        // entry editor
        newEntry: null,         // set by addEntry()
        copyDn: null,           // set by copy dialog
        
        entry: null,            // entry in editor
        attrMap: {
            'integerMatch': 'number',
        },
        selectedOc: null,       // objectClass selection
        newAttr: null,          // auxillary attribute to add
        
        // schema side-panels
        schema: {               // LDAP schema info
            attributes:    [],
            objectClasses: [],
        },
        oc: null,               // objectclass side panel
        attr: null,             // attribute side panel
        hiddenFields: ['desc', 'name', 'names',
            'no_user_mod', 'obsolete', 'oid', 'usage', 'syntax', 'sup'],
    },
    
    created: function() { // Runs on page load
        
        this.reloadTree();
        
        // Get the DN of the current user
        $.get('api/whoami', function( response) {
            window.app.user = response;
        });
        
        // Load the schema
        $.get('api/schema', function( response) {
            window.app.schema = response;
        });
    },
    
    methods: {
        
        // Populate the tree view
        reloadTree: function() {
            $.get('api/tree', function(response) {
                window.app.tree = response;
                dns = {}
                for (item of response) {
                    if (item.parent) item.parent = dns[item.parent];
                    dns[ item.dn] = item;
                }
            });
        },
        
        // hide / show tree elements
        toggle: function( item) {
            item.collapsed = !item.collapsed;
        },
        
        // Populate the "New Entry" form
        addEntry: function() {
            this.newEntry = {
                parent: this.entry.meta.dn,
                name: null,
                rdn: null,
                objectClass: null,
            };
            this.$refs.newRef.show();
        },
        
        // Create anew entry in the main editor
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
                for (let i = 0; i < oc.must.length; ++i) {
                    const must = oc.must[i];
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
        
        // Pop up the copy dialog
        copy: function() {
            this.error = {};
            this.copyDn = this.entry.meta.dn;
            this.$refs.copyRef.show();
        },
        
        // Load copied entry into the editor
        cloneEntry: function( evt) {

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
        
        // load an entry into the editing form
        loadEntry: function( dn, changed) {
            this.newEntry = null;
            this.searchResult = null;
            $.get('api/entry/' + dn, function( response) {
                window.app.entry = response;
                window.app.entry.changed = changed ? changed : [];
            });
        },
        
        reset: function() {
            this.loadEntry( this.entry.meta.dn);
        },
        
        // submit the entry form via AJAX
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
                    if ( data && data.changed && data.changed.length > 0) {
                        window.app.showInfo( '👍 Saved changes');
                    }
                    if (window.app.newEntry)  window.app.reloadTree();
                    window.app.newEntry = null;
                    window.app.loadEntry( dn, data.changed);
                }})
            .fail( function( xhr, errorType, error) {
                window.app.showError( xhr.responseText);
            });
        },
        
        remove: function() {
            $.ajax({
                url:  'api/entry/' + this.entry.meta.dn,
                type: 'DELETE',
                success: function( result) {
                    window.app.showInfo( 'Entry deleted');
                    window.app.entry = null;
                    window.app.reloadTree();
                }
            });
        },
        
        // Get a schema objectClass by name
        getOc: function( name) {
            return this.schema.objectClasses[name.toLowerCase()];
        },
        
        // callback for OC selection dialog
        addOc: function( evt) {
            this.entry.attrs.objectClass.push( this.selectedOc);
            const must = this.schema.objectClasses[
                    this.selectedOc.toLowerCase()].must;
            for (let i = 0; i < must.length; ++i) {
                if (this.entry.meta.required.indexOf( must[i]) == -1) {
                    this.entry.meta.required.push( must[i]);
                }
                if (!this.entry.attrs[ must[i]]) {
                    this.entry.attrs[ must[i]] = [''];
                }
            }
            this.entry = this.clone( this.entry);
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
                    if (a2.names[i].toLowerCase() == n) return a2;
                }
            }
        },
        
        createAttr: function() {
            this.newAttr = null;
            this.$refs.newAttr.show();
        },
        
        addAttr: function( evt) {
            if (!this.newAttr) {
                evt.preventDefault();
                return;
            }
            
            this.entry.attrs[this.newAttr] = [''];
            this.newAttr = null;
        },
        
        // Shallow-copy an object
        clone: function( obj) {
            if (null == obj || "object" != typeof obj) return obj;
            let copy = {};
            for (var attr in obj) {
                if (obj.hasOwnProperty(attr)) copy[attr] = obj[attr];
            }
            return copy;
        },
        
        // Add an empty row in the entry form
        addRow: function( key, values) {
            if (key == 'objectClass') {
                this.$refs.ocref.show();
            }
            else if (values.indexOf('') == -1) {
                values.push('');
                this.entry = this.clone( this.entry);
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

        showInfo: function( msg) {
            this.error = { counter: 5, type: 'success', msg: '' + msg }
        },
        
        showWarning: function( msg) {
            this.error = { counter: 10, type: 'warning', msg: '⚠️ ' + msg }
        },
        
        showError: function( msg) {
            this.error = { counter: 60, type: 'danger', msg: '⛔ ' + msg }
        },
        
    },
    
    computed: {
        
        // All visible tree entries
        treeItems: function() {
            return this.tree.filter( function( item) {
                for (let i = item.parent; i; i=i.parent) {
                    if (i.collapsed) return false;
                }
                return true;
            });
        },
        
        // Choice list of auxillary object classes for the current entry
        aux: function() {
            if (!this.entry) return [];

            return this.entry.meta.aux.map( function( c) {
                return { value: c, text: c };
            });
        },

        // Choice list of all structural object classes
        structural: function() {
            let options = [];
            for (i in this.schema.objectClasses) {
                const oc = this.schema.objectClasses[i];
                if (oc.kind == 'structural') {                    
                    options.push( { value: oc.name, text: oc.name });
                }
            }
            return options;
        },

        // Choice list of RDN attributes for a new entry
        rdn: function() {
            if (!this.newEntry || !this.newEntry.objectClass) return [];
            
            const oc = this.getOc( this.newEntry.objectClass);
            return oc.must.map( function( c) {
                const attr = window.app.getAttr( c);
                return { value: attr.name, text: attr.name };
            });
        },
        
        attrs: function() {
            if (!this.entry || !this.entry.attrs || !this.entry.attrs.objectClass) return [];
            
            let options = [];
            for (let i = 0; i < this.entry.attrs.objectClass.length; ++i) {
                const oc = this.getOc( this.entry.attrs.objectClass[i]);
                for (let j = 0; oc && j < oc.may.length; ++j) {
                    const a = oc.may[j];
                    if (options.indexOf( a) == -1 && !this.entry.attrs[a]) {
                        options.push( a);
                    }
                }
            }
            return options;
        },
    },
})
