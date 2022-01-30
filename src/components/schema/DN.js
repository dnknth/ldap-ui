export function DN(value) {

  function RDN(value) {
    this.value = value;
    this.length = value.length;
    const parts = value.split('=');
    this.attr = parts[0];
    this.name = parts[1];
  }
  
  RDN.prototype = {
    toString: function() { return this.value; },
    valueOf: function() { return this.value; },
  }
  
  this.value = value;
  const parts = value ? value.split(',') : [];
  this.length = parts.length;
  this.rdn = parts.length && parts[0].includes('=')
    ? new RDN(parts[0]) : undefined;
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
}
