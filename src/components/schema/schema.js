"use strict";

export function LdapSchema(json) {
  
  function unique(element, index, array) {
    return array.indexOf(element) == index;
  }

  function RDN(value) {
    this.value = value;
    this.length = value.length;
    const parts = value.split('=');
    this.attr = parts[0];
    this.name = parts[1];
  }

  RDN.prototype = {
    schema: this,
    toString: function() { return this.value; },
    valueOf: function() { return this.value; },
    equals: function(other) {
      return this.schema.attr(this.attr).equals(this.name, other.name);
    },
  };


  function DN(value) {
    this.value = value;
    const parts = value.split(',');
    this.length = parts.length;
    this.rdn = new RDN(parts[0]);
  }
  
  DN.prototype = {
    toString: function() { return this.value; },
    valueOf: function() { return this.value; },
  
    get parent() {
      return !this.value.includes(',') ? undefined
        : new DN(this.value.slice(this.rdn.length + 1));
    },
  
    parents: function(base) {
      const p = this.parent;
      return p && p.value.includes(base || '')
        ? [p].concat(p.parents(base)) : [];
    },

    parts: function() {
      return this.value.split(',').map(rdn => new RDN(rdn));
    },

    equals: function(other) {
      if (this.length != other.length) return false;
      const parts = other.parts;
      return this.parts.every((e, i) => e.equals(parts[i]));
    },
  };


  function ObjectClass(json) {
    Object.assign(this, json);
  }

  ObjectClass.prototype = {
    
    schema: this,
    
    get superClasses() {
      let result = [];
      for (let oc = this; oc; oc = this.schema.oc(oc.sup[0])) result.push(oc);
      return result;
    },
    
    get isStructural() { return this.kind == 'structural'; },

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

    toString: function() { return this.names[0]; },
  };


  function Attribute(json) {
    Object.assign(this, json);
  }

  Attribute.prototype = {
    schema: this,
    toString: function() { return this.names[0]; },
    
    // look up a field across superclasses
    getField: function(name) {
      for (let attr = this; attr; attr = this.schema.attr(attr.sup[0])) {
        const val = attr[name];
        if (val) return val;
      }
    },

    matchRules: {
      "distinguishedNameMatch": (a, b) => new DN(a).equals(new DN(b)),
      "caseIgnoreIA5Match": (a, b) => a.toLowerCase() == b.toLowerCase(),
      "caseIgnoreMatch": (a, b) => a.toLowerCase() == b.toLowerCase(),
      // "generalizedTimeMatch",
      "integerMatch": (a, b) => +a == +b,
      "numericStringMatch": (a, b) => +a == +b,
    },

    equals: function(a, b) {
      const predicate = this.matchRules[this.getField('equality')]
        || ((a, b) => a == b);
      return predicate(a, b);
    },
  };

  function FlatMap(json, ctor) {
    this._objects = [];
    if (!json) return;

    this._objects = Object.getOwnPropertyNames(json)
      .map(prop => ctor ? new ctor(json[prop]) : json[prop]);
    
    this._objects.forEach(obj => obj.names.forEach(
      name => { this[name.toLowerCase()] = obj; }));
  }


  this.attributes = new FlatMap(json.attributes, Attribute);
  this.objectClasses = new FlatMap(json.objectClasses, ObjectClass);
  this.syntaxes = json.syntaxes || [];
  this.DN = DN;

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
};
