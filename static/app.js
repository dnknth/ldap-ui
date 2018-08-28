window.app = new Vue({
    
    // root <div> in page
    el: "#app",
    
    data: {
        user: null,    // logged in user
        
        tree: [],      // complete tree
        treeItems: [], // visible tree
        icons: {       // OC to icon mapping for tree view
            inetOrgPerson:      'address-book', // 'user-circle', 
            organization:       'globe', // 'home', 'school',
            organizationalRole: 'robot', // 'user-tie', 
            organizationalUnit: 'sitemap',
            groupOfNames:       'user-friends',
            person:             'user',
        },
        showTree: true,
        
        entry: null,   // entry in editor
        attrMap: {
            'integerMatch': 'number',
        },
        
        schema: {      // LDAP schema info
            attributes:    [],
            objectClasses: [],
        },
        oc: null,      // objectclass in schema view
        
        attr: null,    // attribute view
        hiddenFields: ['desc', 'name', 'names',
            'no_user_mod', 'obsolete', 'oid', 'usage', 'syntax', 'sup'],
    },
    
    created: function() { // Runs on page load
        
        // Populate the tree view
        $.get('api/tree', function(response) {
            window.app.tree = response;
            dns = {}
            for (item of response) {
                item.collapsed = item.level > 0;
                if (item.parent) item.parent = dns[item.parent];
                dns[ item.dn] = item;
            }
            window.app.buildTree();
        });
        
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
        
        // hide / show tree elements
        toggle: function( item) {
            item.collapsed = !item.collapsed;
            this.buildTree();
        },
        
        // rebuild list of visible tree entries
        buildTree: function() {
            this.treeItems = this.tree.filter( function( item) {
                for (let i = item.parent; i; i=i.parent) {
                    if (i.collapsed) return false;
                }
                return true;
            });
        },
        
        // load an entry into the editing form
        loadEntry: function( dn) {
            $.get('api/entry/' + dn, function(response) {
                window.app.entry = response;
            });
        },
        
        // submit the entry form via AJAX
        onSubmit: function( evt) {
            evt.preventDefault();
            const fd = new FormData( evt.target);
            $.ajax({
                url: 'api/entry/' + window.app.entry.meta.dn,
                data: fd,
                processData: false,
                contentType: false,
                type: 'POST',
                success: function( data) {
                    alert( data);
                }
            });
        },
        
        // Get a schema objectClass by name
        getOc: function( name) {
            return this.schema.objectClasses[name.toLowerCase()];
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
        addRow: function( values) {
            if (values.indexOf('') == -1) {
                values.push('');
                this.entry = this.clone( this.entry);
            }
        },
        
        required: function( key) {
            return this.entry.meta.required.indexOf( key) != -1;
        },
        
        fieldType: function( attr) {
            if (attr == 'userPassword') return 'password';
            return this.attrMap[ this.getAttr(attr).equality] || 'text';
        },
        
        isStructural: function( key, val) {
            return key == 'objectClass'
                && val == this.entry.attrs.structuralObjectClass[0];
        },
        
        search: function( evt) {
            evt.preventDefault();
            const fd = new FormData( evt.target);
            $.get('api/search/' + $('input#q').val(), function(response) {
                window.app.entry = response;
            });
        },

    },
    
    computed: {
    },
})
