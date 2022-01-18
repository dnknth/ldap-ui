"use strict";

function LdapSchema(json) {
  
  // copy properties from a given object
  function ShallowCopy(json, ctor) {
    for (let prop in json) {
      if (json.hasOwnProperty(prop)) {
        this[prop] = ctor ? new ctor(json[prop]) : json[prop];
      }
    }
  }

  function ObjectClass(json) {
    ShallowCopy.call(this, json);
  }

  ObjectClass.prototype = {
    
    schema: this,
    
    get isStructural() {
      return this.kind == 'structural';
    },

    // List all structural attributes for a class
    get structural() {
      let result = [];
      for (let oc = this; oc; oc = this.schema.oc(oc.sup[0])) {
        for (let i in oc.must) {
            const name = this.schema.attr(oc.must[i]).name;
            if (name != 'objectClass') result.push(name);
        }
      }
      return result;
    },
    
    // collect values from a field, across all superclasses
    getAll: function(name) {
      let result = [];
      for (let oc = this; oc; oc = this.schema.oc(oc.sup[0])) {
        const val = oc[name];
        if (val) result = result.concat(val);
      }
      result.sort();
      return result;
    },

    toString: function() {
      return this.names[0];
    },
  }
  
  function Attribute(json) {
    ShallowCopy.call(this, json);
  }

  Attribute.prototype = {
    
    schema: this,
    
    // look up a field across superclasses
    getField: function(name) {
      for (let attr = this; attr; attr = this.schema.attr(attr.sup[0])) {
        const val = attr[name];
        if (val) return val;
      }
    },

    toString: function() {
      return this.names[0];
    },
  }

  function FlatMap(json, ctor) {
    this._objects = [];
    if (!json) return;
    
    for (let prop in json) {
      if (json.hasOwnProperty(prop)) {
        const obj = ctor ? new ctor(json[prop]) : json[prop];
        this._objects.push(obj);
        for (let i = 0; i < obj.names.length; ++i) {
          const name = obj.names[i].toLowerCase();
          this[name] = obj;
        }
      }
    }
  }
  
  this.attributes = new FlatMap(json.attributes, Attribute);
  this.objectClasses = new FlatMap(json.objectClasses, ObjectClass);
  this.syntaxes = json.syntaxes || [];

  this.structural = [];
  for (let i in this.objectClasses._objects) {
    const oc = this.objectClasses._objects[i];
    if (oc.isStructural) this.structural.push(oc.name);
  }
}

LdapSchema.prototype = {
  attr: function(name) {
    return name ? this.attributes[name.toLowerCase()] : undefined;
  },
  
  oc: function(name) {
    return name ? this.objectClasses[name.toLowerCase()] : undefined;
  }
}