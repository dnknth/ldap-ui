"use strict";

export function LdapSchema(json) {
  
  // copy properties from a given object
  function ShallowCopy(json, ctor) {
    for (let prop in json) {
      if (Object.prototype.hasOwnProperty.call(json, prop)) {
        this[prop] = ctor ? new ctor(json[prop]) : json[prop];
      }
    }
  }

  function unique(element, index, array) { 
    return array.indexOf(element) == index;
  }

  function ObjectClass(json) {
    ShallowCopy.call(this, json);
  }

  ObjectClass.prototype = {
    
    schema: this,
    
    get superClasses() {
      let result = [];
      for (let oc = this; oc; oc = this.schema.oc(oc.sup[0])) result.push(oc);
      return result;
    },
    
    get isStructural() {
      return this.kind == 'structural';
    },

    // collect values from a field, across all superclasses
    getAttributes: function(name) {
      const result = this.superClasses
        .map(oc => oc[name])
        .filter(attrs => attrs)
        .flat()
        .map(attr => this.schema.attr(attr).name)
        .filter(unique);
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
      if (Object.prototype.hasOwnProperty.call(json, prop)) {
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

  this.structural = this.objectClasses._objects
    .filter(oc => oc.isStructural)
    .map(oc => oc.name);
}

LdapSchema.prototype = {
  attr: function(name) {
    return name ? this.attributes[name.toLowerCase()] : undefined;
  },
  
  oc: function(name) {
    return name ? this.objectClasses[name.toLowerCase()] : undefined;
  }
}
