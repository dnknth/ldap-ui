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

        // default attribute syntax (constant)
        directoryString: '1.3.6.1.4.1.1466.115.121.1.15',

        // authentication
        user: null,             // logged in user
        
        // tree view
        tree: [],               // the tree that has been loaded so far
        treeMap: {},            // DN -> item mapping to check entry visibility
        icons: {                // OC -> icon mapping in tree
            inetOrgPerson:      'address-book',
            organization:       'globe',
            organizationalRole: 'android',
            organizationalUnit: 'sitemap',
            groupOfNames:       'users',
            groupOfUniqueNames: 'users',
            posixGroup:         'users',
            person:             'user',
            account:            'user',
            krbContainer:       'lock',
            krbRealmContainer:  'globe',
            krbPrincipal:       'user-o',
        },

        treeOpen: true,         // Is the tree visible?

        // alerts
        error: {},              // status alert
        
        // search
        searchResult: null,     // search result data
        searchPopup: null,      // search result HTML popup
        
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
        hiddenFields: [         // not shown in schema panel
            'desc', 'name', 'names',
            'no_user_mod', 'obsolete', 'oid',
            'usage', 'syntax', 'sup' ],
        
        password: {},
        passwordOk: false,      // old password verified?
        passwordsMatch: false,  // new password matches repetition?
        
        ldifData: '',

        dropdownChoices: [],    // list of search results for DN attributes
        dropdownId: null,       // focused DN input ID
        dropdownMenu: null,     // <ul> with completions

        subtree: null,          // subordinate elements in delete confirmation

        focused: null,          // currently focused input
    },
    
    created: function() { // Runs on page load
        
        // Get the DN of the current user
        request( { url: 'api/whoami'}).then( function( xhr) {
            app.user = JSON.parse( xhr.response);
        }).catch( function( xhr) {
            app.showException( xhr.response);
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
        
        // Focus an element on second next draw
        focus: function( id) {
            Vue.nextTick( function() {
                Vue.nextTick( function() {
                    const el = document.getElementById( id);
                    if (el) el.focus();
                });
            });
        },

        // Clean up UI state on focus changes and clicks
        focusHandler: function( evt) {
            const el = event.target,
                cl = el.classList;
            if (el.id != 'search' && !cl.contains( 'search-item')) {
                this.clearSearch();
            }
            if (el.id != this.dropdownId && !cl.contains( 'dropdown-item')) {
                this.clearDropdown();
            }

            if (el.tagName == 'INPUT' && el.id && el.form.id == 'entry-form')  {
                this.focused = el.id;
            }
        },

        // Reload the subtree at entry with given DN
        reload: function( dn) {
            const treesize = this.tree.length;
            let pos = this.tree.indexOf( this.treeMap[ dn]);
            return request( { url: 'api/tree/' + dn }).then( function( xhr) {
                const response = JSON.parse( xhr.response);

                response.sort( function( a, b) {
                    return a.dn.toLowerCase().localeCompare( b.dn.toLowerCase());
                });
                
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
            return dn.split(',')[0].replace( /^cn=/, '').replace( /^krbPrincipalName=/, '');
        },
        
        // Hide / show tree elements
        toggle: function( item) {
            item.open = !item.open;
            this.tree = this.tree.slice(); // force redraw
            if (item.open) this.reload( item.dn);
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

            this.entry = {
                meta: {
                    dn: this.newEntry.rdn + '=' + this.newEntry.name + ',' + this.newEntry.parent,
                    aux: [],
                    required: [],
                    binary: [],
                },
                attrs: {
                    objectClass: [ this.newEntry.objectClass],
                },
            };
            
            this.entry.attrs[this.newEntry.rdn] = [this.newEntry.name];
            
            // Traverse objectClass parents
            for( let oc = this.getOc( this.newEntry.objectClass); oc; ) {
                
                if (oc.kind != 'structural') {
                    this.entry.attrs.objectClass.push( oc.name);
                }

                // Add required attributes
                for (let i = 0; i < oc.must.length; ++i) {
                    let must = oc.must[i];
                    if (!this.entry.attrs[ must]) {
                        this.entry.attrs[ must] = [''];
                    }
                    if (this.entry.meta.required.indexOf( must) == -1) {
                        this.entry.meta.required.push( must);
                    }
                }
                if (!oc.sup || !oc.sup.length || oc.sup[0] == 'top') break;
                oc = this.getOc( oc.sup[0]);
            }
            this.$refs.newRef.hide();

            // Work-around partial rendering bug
            Vue.nextTick( function () {
                document.querySelectorAll('input').forEach( function( el) {
                    el.removeAttribute( 'disabled');
                });
                document.querySelectorAll('input.disabled').forEach( function( el) {
                    el.setAttribute( 'disabled', 'disabled');
                });
            });

            // Focus on first empty field
            const keys = Object.keys( this.entry.attrs);
            for (let i = 0; i < keys.length; ++i) {
                const key = keys[i];
                if (this.entry.attrs[key] == '') {
                    this.focus( key + '-0');
                }
            }
        },
        
        // Bring up the 'rename' dialog
        renameDialog: function() {
            this.newRdn = null;
            this.$refs.renameRef.show();
        },

        // Choice list of possible rdns
        renameRdns: function() {
            if (!this.entry) return []

            const dn = this.entry.meta.dn,
                rdn = dn.split('=')[0];
            return Object.keys( this.entry.attrs).filter( 
                function( e) {
                    return e != rdn;
                }
            );
        },
        
        // Change the RDN for an entry
        renameEntry: function( evt) {
            const dn = this.entry.meta.dn;
                
            const rdnAttr = this.entry.attrs[this.newRdn];
            if (!rdnAttr || !rdnAttr[0]) {
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
                app.showException( xhr.response);
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
        },
        
        // Verify an existing password
        // This is optional for administrative changes
        // but required to change the current user's password
        checkOldPassword: function() {
            if (!this.password.old || this.password.old.length == 0) {
                app.passwordOk = null;
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
                app.showException( xhr.response);
            });
        },
        
        // Verify that the new password is repeated correctly
        checkNewPassword: function() {
            this.passwordsMatch = this.password.new1
                && this.password.new1.length > 0
                && this.password.new1 == this.password.new2;
        },
        
        // Update password
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
                app.entry.attrs['userPassword'] = [ JSON.parse( xhr.response) ];
                app.$refs.pwRef.hide();
            }).catch( function( xhr) {
                app.showException( xhr.response);
                app.$refs.pwRef.hide();
            });
        },
        
        // Update password
        deletePassword: function( evt) {
            if (this.user != this.entry.meta.dn) {
                this.entry.attrs['userPassword'] = [];
            }
        },
        
        // Pop up the copy dialog
        copyDialog: function() {
            this.error = {};
            this.copyDn = this.entry.meta.dn;
            this.$refs.copyRef.show();
        },
        
        // Show the LDIF import dialog
        importDialog: function() {
            this.error = {};
            this.ldifData = '';
            this.ldifFile = null;
            this.$refs.importRef.show();
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
                app.showException( xhr.response);
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

            if (rdnpart.length != 2) {
                this.copyDn = null;
                this.showError( 'Invalid RDN: ' + parts[0]);
                return;
            }
            
            this.entry.attrs[rdn] = [rdnpart[1]];
            this.entry.meta.dn = this.copyDn;
            this.newEntry = { dn: this.copyDn }
            this.copyDn = null;
            this.$refs.copyRef.hide();
        },
        
        // Load an entry into the editing form
        loadEntry: function( dn, changed) {
            const oldEntry = this.entry;
            this.newEntry = null;
            this.clearDropdown();

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
                    // Focus on last focused input or first editable attribute
                    const input = document.querySelector( '#' + app.focused)
                        || document.querySelector( '#entry input:not([disabled])');
                    if (input) input.focus();
                });
                // Clear notifications on DN change
                if (oldEntry && oldEntry.meta && oldEntry.meta.dn != dn) {
                    app.error = {};
                    app.focused = null;
                }
                document.title = dn.split( ',')[0];
            });
        },

        // auto-complete form values
        complete: function( evt) {

            // Avoid AJAX calls without results
            const q = evt.target.value;
            if (q.length < 2 || q.indexOf(',') != -1) {
                this.clearDropdown();
                return;
            }

            const attr = evt.target.id.split('-', 1);
            if (evt.key.length == 1 && this.getEquality( attr[0]) == 'distinguishedNameMatch') {
                this.dropdownId = evt.target.id;
                request( { url: 'api/search/' + q }
                ).then( function( xhr) {
                    const response = JSON.parse( xhr.response);
                    app.clearDropdown();
                    for (let i = 0; i < response.length; ++i) {
                        app.dropdownChoices.push( response[i].dn);
                    }
                    Vue.nextTick( function() {
                        const dropdown = document.getElementById( 'dropdown');
                        if (app.dropdownChoices.length) {
                            dropdown.className = '';
                            app.dropdownMenu = Popper.createPopper(
                                document.getElementById( app.dropdownId),
                                dropdown, {
                                    modifiers: [ {
                                        name: 'offset',
                                        options: { offset: [0, -8] },
                                    } ]
                                });
                            dropdown.setAttribute( 'data-show', '');
                        }
                    });
                }).catch( function( xhr) {
                    app.clearDropdown();
                });
            }
        },

        // use an auto-completion choice
        selectCompletion: function( evt) {
            const el = document.getElementById( this.dropdownId),
                attr = this.dropdownId.split( '-')[0], 
                index = this.dropdownId.split( '-')[1];
            this.entry.attrs[attr][index] = el.value = evt.target.innerText;
            this.focus( this.dropdownId);
            this.clearDropdown();
        },
        
        // reset choice list
        clearDropdown: function( evt) {
            if (this.dropdownMenu) this.dropdownMenu.destroy();
            this.dropdownMenu = null;
            this.dropdownChoices = [];
            const dropdown = document.getElementById( 'dropdown');
            if (dropdown) {
                dropdown.removeAttribute( 'data-show');
                dropdown.className = 'hidden';
            }
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
                app.showException( xhr.response);
            });
        },
        
        // Special fields
        binary: function( key) {
            if (key == 'userPassword') return false; // Corner case with octetStringMatch
            return this.entry.meta.binary.indexOf( key) != -1;                    
        },
        
        // Special fields
        disabled: function( key) {
            return key == 'userPassword'
                || key == this.entry.meta.dn.split( '=')[0]
                || this.binary( key);
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
                app.showException( xhr.response);
            });
        },

        // List subordinate elements of a DN
        getSubtree: function() {
            const dn = this.entry.meta.dn;
            request({ url:  'api/subtree/' + dn
            }).then( function( xhr) {
                app.subtree = JSON.parse( xhr.response);
            }).catch( function( xhr) {
                app.showException( xhr.response);
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
                app.showException( xhr.response);
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

        // look up a field, traversing suberclasses
        getField: function( attr, name) {
            do {
                const val = attr[name];
                if (val) return val;
                attr = this.getAttr( attr.sup[0]);
            } while (attr);
        },
        
        // Get an attribute syntax
        getSyntax: function( name) {
            const a = this.getAttr( name);
            if (a) return this.schema.syntaxes[
                this.getField( a, 'syntax') || this.directoryString];
        },

        // Get the equality rule name for an attribute
        getEquality: function( name) {
            return this.getField( this.getAttr( name), 'equality');
        },
        
        // Show popup for attribute selection
        attrDialog: function() {
            this.newAttr = this.attrs[0];
            this.$refs.attrRef.show();
        },
        
        // Add the selected attribute
        addAttr: function( evt) {

            const attr = this.newAttr;
            
            // check for binary attributes
            this.entry.attrs[ attr] = [''];
            if (this.getSyntax( attr).not_human_readable) {
                this.entry.meta.binary.push( attr);
            }

            // Delay DOM update
            Vue.nextTick( function () {
                document.querySelectorAll('input').forEach( function( el) {
                    el.removeAttribute( 'disabled');
                });
                document.querySelectorAll('input.disabled').forEach( function( el) {
                    el.setAttribute( 'disabled', 'disabled');
                });
                if (attr == 'userPassword') {
                    app.pwDialog();
                }
            });

            this.focus( attr + '-0');

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
            }
            else if (values.indexOf('') == -1) {
                values.push('');
                this.focus( key + '-' + (values.length -1));
            }
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
                app.showException( xhr.response);
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
                app.clearSearch();
                app.error = {};

                if (!response || !response.length) {
                    app.showWarning( 'No search results');
                }
                else if (response.length == 1) {
                    // load single result for editing
                    app.loadEntry( response[0].dn);
                }
                else { // multiple results
                    app.searchResult = response;
                    Vue.nextTick( function() {
                        const popup = document.getElementById( 'search-popup');
                        popup.className = '';
                        app.searchPopup = Popper.createPopper(
                            document.getElementById( 'search'),
                            popup, {
                                modifiers: [ {
                                    name: 'offset',
                                    options: { offset: [0, 4] },
                                } ]
                            });
                        popup.setAttribute( 'data-show', '');
                    });
                }
            }).catch( function( xhr) {
                app.showException( xhr.response);
            });
        },

        clearSearch: function( evt) {
            if (this.searchPopup) this.searchPopup.destroy();
            this.searchPopup = null;
            app.searchResult = null;
            const popup = document.getElementById( 'search-popup');
            if (popup) {
                popup.removeAttribute( 'data-show');
                popup.className = 'hidden';
            }
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

        showException: function( msg) {
            const span = document.createElement('span');
            span.innerHTML = msg;
            const titles = span.getElementsByTagName('title');
            for (let i = 0; i < titles.length; ++i) {
                span.removeChild( titles[i]);
            }
            let text = '';
            const headlines = span.getElementsByTagName('h1');
            for (let i = 0; i < headlines.length; ++i) {
                text = text + headlines[i].textContent + ': ';
                span.removeChild( headlines[i]);
            }
            this.showError( text + span.textContent);
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
