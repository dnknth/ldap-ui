"use strict";

/* See: https://stackoverflow.com/questions/30008114/how-do-i-promisify-native-xhr#30008115
 * 
 * opts = {
 *   method: String,
 *   url: String,
 *   data: String | Object,
 *   headers: Object,
 *   responseType: String,
 *   binary: Boolean,
 * }
 */
function request( opts) {
  return new Promise( function( resolve, reject) {
    var xhr = new XMLHttpRequest();
    xhr.open( opts.method || 'GET', opts.url);
    if (opts.responseType) xhr.responseType = opts.responseType;
    xhr.onload = function () {
      if (this.status >= 200 && this.status < 300) {
        resolve(xhr);
      } else {
        reject( this);
      }
    };
    xhr.onerror = function () {
      reject( this);
    };
    if (opts.headers) {
      Object.keys(opts.headers).forEach(function (key) {
        xhr.setRequestHeader(key, opts.headers[key]);
      });
    }
    var params = opts.data;
    // We'll need to stringify if we've been given an object
    // If we have a string, this is skipped.
    if (params && typeof params === 'object' && !opts.binary) {
      params = Object.keys(params).map(function (key) {
        return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
      }).join('&');
    }
    xhr.send(params);
  });
}


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
            account:            'user-tie',
            krbContainer:       'lock',
            krbRealmContainer:  'globe',
            krbPrincipal:       'user-lock',

        },
        treeOpen: true,         // Is the tree visible?

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
        
        password: {},
        passwordOk: false,
        
        ldifData: '',
    },
    
    created: function() { // Runs on page load
        
        // Get the DN of the current user
        request( { url: 'api/whoami'}).then( function( xhr) {
            app.user = JSON.parse( xhr.response);
        });
        
        // Populate the tree view
        this.reload( 'base');
        
        // Load the schema
        request( { url: 'api/schema' }).then( function( xhr) {
            app.schema = JSON.parse( xhr.response);
            app.schema.structural = [];
            for (let n in app.schema.objectClasses) {
                const oc = app.schema.objectClasses[n];
                if (oc.kind == 'structural') {
                    app.schema.structural.push( oc.name);
                }
            }
        });

        this.focus('search');
    },
    
    methods: {
        
        // Focus an element on next draw
        focus: function( id) {
            Vue.nextTick( function() {
                Vue.nextTick( function() {
                    const el = document.getElementById( id);
                    if (el) el.focus();
                });
            });
        },
        
        // Reload the subtree at entry with given DN
        reload: function( dn) {
            const treesize = this.tree.length;
            let pos = this.tree.indexOf( this.treeMap[ dn]);
            return request( { url: 'api/tree/' + dn }).then( function( xhr) {
                const response = JSON.parse( xhr.response);
                
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
                app.reload( pdn).then( function() {
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
        
        // Shorten a DN for readability
        label: function( dn) {
            return dn.split(',')[0].replace( /^cn=/, '');
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
            this.focus('newoc');
        },
        
        // Create a new entry in the main editor
        createEntry: function( evt) {
            this.entry = null;
            if (!this.newEntry || !this.newEntry.objectClass
                || !this.newEntry.rdn || !this.newEntry.name) {
                    evt.preventDefault();
                    return;
            }

            this.entry = {
                meta: {
                    dn: this.newEntry.rdn + '=' + this.newEntry.name + ',' + this.newEntry.parent,
                    aux: [],
                    required: [],
                    binary: [],
                },
                attrs: {
                    objectClass: [],
                },
            };
            
            this.entry.attrs[this.newEntry.rdn] = [this.newEntry.name];
            
            // Add required attributes and objectClass parents
            let oc = this.getOc( this.newEntry.objectClass);
            this.entry.attrs.objectClass.push( oc.name);
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
                if (oc.kind != 'structural') {
                    this.entry.attrs.objectClass.push( oc.name);
                }
                if (!oc.sup || !oc.sup.length) break;
                oc = this.getOc( oc.sup[0]);
            }
            this.entry.meta.aux = [];
        },
        
        // Bring up the 'rename' dialog
        renameDialog: function() {
            this.newRdn = null;
            this.$refs.renameRef.show();
            this.focus('renamerdn');
        },
        
        // Change the RDN for an entry
        renameEntry: function( evt) {
            const dn = this.entry.meta.dn;
                
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
            request( { url: 'api/rename/' + rdn + '/' + dn }).then( function( xhr) {
                app.entry = JSON.parse( xhr.response);
                const parent = app.parent( dn),
                    dnparts = dn.split(',');
                if (parent) app.reload( parent.dn);
                dnparts.splice( 0, 1, rdn);
                app.loadEntry( dnparts.join(','));
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Pop up the copy dialog
        pwDialog: function() {
            this.error = {};
            this.password = {
                old: null,
                new1: '',
                new2: '',
            };
            this.passwordOk = null;
            this.$refs.pwRef.show();
            this.focus('oldpw');
        },
        
        // Verify an existing password
        // This is optional for administrative changes
        // but required to change the current user's password
        checkPassword: function() {
            if (!this.password.old || this.password.old.length == 0) {
                return;
            }
            request({
                url:  'api/entry/password/' + this.entry.meta.dn,
                method: 'POST',
                data: JSON.stringify( { check: this.password.old }),
                headers: {
                    'Content-Type': 'application/json; charset=utf-8',
                }
            }).then( function( xhr) {
                app.passwordOk = JSON.parse( xhr.response);
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Update passwords
        changePassword: function( evt) {
            
            // new passwords must match
            // old password is required for current user
            if (this.password.new1 == '' || this.password.new1 != this.password.new2
                || (this.user == this.entry.meta.dn
                    && (!this.password.old || this.password.old == ''))) {
                evt.preventDefault();
                return;
            }
            
            request({
                url:  'api/entry/password/' + this.entry.meta.dn,
                method: 'POST',
                data: JSON.stringify( this.password),
                headers: {
                    'Content-Type': 'application/json; charset=utf-8',
                }
            }).then( function( xhr) {
                app.showInfo( '👍 Password changed');
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Pop up the copy dialog
        copyDialog: function() {
            this.error = {};
            this.copyDn = this.entry.meta.dn;
            this.$refs.copyRef.show();
            this.focus('copyDn');
        },
        
        // Show the LDIF import dialog
        importDialog: function() {
            this.error = {};
            this.ldifData = '';
            this.ldifFile = null;
            this.$refs.importRef.show();
            this.focus('copyDn');
        },
        
        // Load LDIF from file
        readLdif: function( evt) {
            const file = evt.target.files[0],
                reader = new FileReader();
            reader.onload = function() {
                app.ldifData = reader.result;
                evt.target.value = null;
            }
            reader.readAsText( file);
        },
        
        // Import LDIF
        importLdif: function( evt) {
            if (!this.ldifData) {
                evt.preventDefault();
                return;
            }
            request({
                url:  'api/ldif',
                method: 'POST',
                data: this.ldifData,
                headers: {
                    'Content-Type': 'text/plain; charset=utf-8',
                }
            }).then( function( xhr) {
                app.$refs.importRef.hide();
                app.reload( app.tree[0].dn);
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
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
            const oldEntry = this.entry;
            this.newEntry = null;
            this.searchResult = null;
            this.reveal( dn);
            request( { url: 'api/entry/' + dn }).then( function( xhr) {
                app.entry = JSON.parse( xhr.response);
                app.entry.changed = changed || [];
                Vue.nextTick( function () {
                    // Work-around partial rendering bug
                    document.querySelectorAll('input').forEach( function( el) {
                        el.removeAttribute( 'disabled');
                    });
                    document.querySelectorAll('input.disabled').forEach( function( el) {
                        el.setAttribute( 'disabled', 'disabled');
                    });
                });
                // Clear notifications on DN change
                if (oldEntry && oldEntry.meta && oldEntry.meta.dn != dn) {
                    app.error = {};
                }
            });
        },

        // auto-complete form values
        complete: function( evt) {
            console.log( evt);
            // FIXME: stub
        },
        
        // Download LDIF
        ldif: function() {
            request( { url: 'api/ldif/' + this.entry.meta.dn,
                responseType: 'blob'
            }).then( function( xhr) {
                var a = document.createElement("a"),
                    url = URL.createObjectURL( xhr.response);
                a.href = url;
                a.download = app.entry.meta.dn.split(',')[0].split('=')[1] + '.ldif';
                document.body.appendChild(a);
                a.click();
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Special fields
        binary: function( key) {
            return this.entry.meta.binary.indexOf( key) != -1;
        },
        
        // Special fields
        disabled: function( key) {
            return this.binary( key)
                || key == 'userPassword'
                || key == this.entry.meta.dn.split( '=')[0];
        },
        
        // Submit the entry form via AJAX
        change: function( evt) {
            this.entry.changed = [];
            this.error = {};
            const dn = this.entry.meta.dn;
            
            request({
                url:  'api/entry/' + dn,
                method: this.newEntry ? 'PUT' : 'POST',
                data: JSON.stringify( this.entry.attrs),
                headers: {
                    'Content-Type': 'application/json; charset=utf-8',
                }
            }).then( function( xhr) {
                const data = JSON.parse( xhr.response);
                if ( data && data.changed && data.changed.length) {
                    app.showInfo( '👍 Saved changes');
                }
                if (app.newEntry) {
                    app.reload( app.parent( dn).dn);
                }
                app.newEntry = null;
                app.loadEntry( dn, data.changed);
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Delete an entry
        remove: function() {
            const dn = this.entry.meta.dn;
            request({ url:  'api/entry/' + dn, method: 'DELETE'
            }).then( function() {
                app.showInfo( 'Deleted entry: ' + dn);
                app.entry = null;
                app.reload( app.parent( dn).dn);
            }).catch( function( xhr) {
                app.showError( xhr.response);
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
            for (let att in this.schema.attributes) {
                const a2 = this.schema.attributes[att];
                for (let i = 0; i < a2.names.length; ++i) {
                    let name = a2.names[i];
                    if (name.toLowerCase() == n) return a2;
                }
            }
        },
        
        // Get an attribute syntax
        getSyntax: function( name) {
            const a = this.getAttr( name);
            if (a) return this.schema.syntaxes[ a.syntax];
        },
        
        // Show popup for attribute selection
        attrDialog: function() {
            this.newAttr = null;
            this.$refs.attrRef.show();
            this.focus('newattr');
        },
        
        // Add the selected attribute
        addAttr: function( evt) {

            const attr = this.newAttr;

            if (!attr) {
                evt.preventDefault();
                return;
            }
            
            // check for binary attributes
            this.entry.attrs[attr] = [''];
            if (this.getSyntax(attr).not_human_readable) {
                this.entry.meta.binary.push(attr);
            }

            // Close popup
            this.newAttr = null;
            if (attr == 'jpegPhoto') {
                this.$refs.photoRef.show();
            }
        },
                
        // Add an empty row in the entry form
        addRow: function( key, values) {
            if (key == 'objectClass') {
                this.$refs.ocRef.show();
                this.focus('oc-select');
            }
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
        
        // add an image
        addBlob: function( evt) {
            
            if (!evt.target.files) return;
            
            const fd = new FormData();
            fd.append( "blob", evt.target.files[0])
            request({
                url:  'api/blob/jpegPhoto/0/' + app.entry.meta.dn,
                method: 'PUT',
                data: fd,
                binary: true,
            }).then( function( xhr) {
                evt.target.value = null;
                app.$refs.photoRef.hide()
                const data = JSON.parse( xhr.response);
                app.loadEntry( app.entry.meta.dn, data.changed);
            }).catch( function( xhr) {
                app.$refs.photoRef.hide();
                app.showError( xhr.response);
            });
        },
        
        // remove an image
        deleteBlob: function( key, index) {
            
            request({
                url:  'api/blob/' + key + '/' + index + '/' + app.entry.meta.dn,
                method: 'DELETE',
            }).then( function( xhr) {
                const data = JSON.parse( xhr.response);
                app.loadEntry( app.entry.meta.dn, data.changed);
            }).catch( function( xhr) {
                app.showError( xhr.response);
            });
        },
        
        // Is the given value a structural object class?
        isStructural: function( key, val) {
            return key == 'objectClass'
                && this.schema.structural.indexOf( val) != -1;
        },
        
        // Run a search against the directory
        search: function( evt) {
            const q = document.getElementById('search').value;
            
            request( { url: 'api/search/' + q }
            ).then( function( xhr) {
                const response = JSON.parse( xhr.response);
                app.searchResult = null;
                app.error = {};

                if (!response || !response.length) {
                    app.showWarning( 'No search results');
                }
                else if (response.length == 1) {
                    // load single result for editing
                    app.loadEntry( response[0].dn);
                }
                else { // multiple results
                    app.entry = null;
                    app.searchResult = response;
                }
            }).catch( function( xhr) {
                app.showError( xhr.response);
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
            if (!this.newEntry || !this.newEntry.objectClass) return [];
            let oc = this.newEntry.objectClass, structural = [];
            while( oc) {
                const cls = this.getOc( oc);
                for (let i in cls.must) {
                    const name = app.getAttr( cls.must[i]).name;
                    if (name != 'objectClass') {
                        structural.push( name);
                    }
                }
                oc = cls.sup.length > 0 ? cls.sup[0] : null;
            }
            return structural;
        },
        
        // Choice list for new attribute selection popup
        attrs: function() {
            if (!this.entry || !this.entry.attrs || !this.entry.attrs.objectClass) return [];
            
            let options = [];
            for (let i = 0; i < this.entry.attrs.objectClass.length; ++i) {
                let key = this.entry.attrs.objectClass[i];
                while (key) {
                    const cls = this.getOc( key),
                        may = cls.may;
                    for (let j = 0; j < may.length; ++j) {
                        let a = may[j];
                        if (options.indexOf( a) == -1 && !this.entry.attrs[a]) {
                            options.push( a);
                        }
                    }
                    key = cls.sup.length > 0 ? cls.sup[0] : null;
                }
            }
            options.sort();
            return options;
        },
    },
})
