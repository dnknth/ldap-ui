"use strict";

export function LdapSchema(json) {
  
  function unique(element, index, array) {
    return array.indexOf(element) == index;
  }

  function RDN(value) {
    this.text = value;
    const parts = value.split('=');
    this.attrName = parts[0].trim();
    this.value = parts[1].trim();
  }

  RDN.prototype = {
    toString: function() { return this.text; },

    eq: function(other) {
      return other
        && this.attr.eq(other.attr)
        && this.attr.matcher(this.value, other.value);
    },

    get attr() {
      return this.$attributes.$get(this.attrName);
    },
  };

  function DN(value) {
    this.text = value;
    const parts = value.split(',');
    this.rdn = new RDN(parts[0]);
    this.parent = parts.length == 1 ? undefined
      : new DN(value.slice(parts[0].length + 1));
  }
  
  DN.prototype = {
    toString: function() { return this.text; },

    eq: function(other) {
      if (!other || !this.rdn.eq(other.rdn)) return false;
      if (!this.parent && !other.parent) return true;
      return this.parent && this.parent.eq(other.parent);
    },
  };

  function ObjectClass(json) {
    Object.assign(this, json);
  }

  ObjectClass.prototype = {
    get structural() { return this.kind == 'structural'; },

    // gather values from a field across all superclasses
    $collect: function(name) {
      let attributes = [];
      for (let oc = this; oc; oc = oc.$super) {
        const attrs = oc[name];
        if (attrs) attributes.push(attrs);
      }

      const result = attributes.flat()
        .map(attr => this.$attributes.$get(attr).name)
        .filter(unique);
      result.sort();
      return result;
    },

    toString: function() { return this.names[0]; },

    get $super() {
      const parent = Object.getPrototypeOf(this);
      return parent.sup ? parent : undefined;
    },
  };

  function Attribute(json) {
    Object.getOwnPropertyNames(json)
      .forEach(prop => {
        const value = json[prop];
        if (value !== null) this[prop] = value;
      });
  }

  Attribute.prototype = {
    toString: function() { return this.names[0]; },

    matchRules: {
      // See: https://ldap.com/matching-rules/
      distinguishedNameMatch: (a, b) => new DN(a).eq(new DN(b)),
      caseIgnoreIA5Match: (a, b) => a.toLowerCase() == b.toLowerCase(),
      caseIgnoreMatch: (a, b) => a.toLowerCase() == b.toLowerCase(),
      // generalizedTimeMatch: ...
      integerMatch: (a, b) => +a == +b,
      numericStringMatch: (a, b) => +a == +b,
      octetStringMatch: (a, b) => a == b,
    },

    get matcher() {
      return this.matchRules[this.equality]
        || this.matchRules.octetStringMatch;
    },

    eq: function(other) { return other && this.oid == other.oid; },

    get binary() {
      if (this.equality == 'octetStringMatch') return undefined;
      return this.$syntax.not_human_readable;
    },

    get $syntax() { return this.$syntaxes[this.syntax]; },

    get $super() {
      const parent = Object.getPrototypeOf(this);
      return parent.sup ? parent : undefined;
    },
  };

  function Syntax(json) {
    Object.assign(this, json);
  }

  Syntax.prototype = {
    toString: function() { return this.desc; },
  };

  function PropertyMap(json, ctor, prop) {
    Object.getOwnPropertyNames(json || {})
      .map(prop => new ctor(json[prop]))
      .forEach(obj => { this[obj[prop]] = obj; });
  }

  function FlatPropertyMap(json, ctor, prop) {
    this.$values = Object.getOwnPropertyNames(json || {})
      .map(key => new ctor(json[key]));
    
    // Map objects to each available prop value
    this.$values.forEach(obj => obj[prop].forEach(
      key => { this[key.toLowerCase()] = obj; }));

    // Model object inheritance as JS prototype chain
    this.$values.forEach(obj => {
      const key = obj.sup[0],
        parent = key ? this[key.toLowerCase()] : undefined;
      if (parent) Object.setPrototypeOf(obj, parent);
    });

    this.$get = function(name) {
      return name ? this[name.toLowerCase()] : undefined;
    };
  }

  // LdapSchema constructor
  this.DN = DN;
  this.RDN = RDN;
  this.Attribute = Attribute;
  this.ObjectClass = ObjectClass;

  Attribute.prototype.$syntaxes = new PropertyMap(json.syntaxes, Syntax, 'oid');
  ObjectClass.prototype.$attributes = new FlatPropertyMap(json.attributes, Attribute, 'names'),
  RDN.prototype.$attributes = ObjectClass.prototype.$attributes;
  ObjectClass.values = new FlatPropertyMap(json.objectClasses, ObjectClass, 'names');

  this.attr = (name) => ObjectClass.prototype.$attributes.$get(name);
  this.oc = (name) => ObjectClass.values.$get(name);
  this.search = (q) => ObjectClass.prototype.$attributes.$values
    .filter(attr => attr.name.toLowerCase().startsWith(q.toLowerCase()));
}
