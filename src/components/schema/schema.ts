"use strict";

function unique(element: unknown, index: number, array: Array<unknown>): boolean {
  return array.indexOf(element) == index;
}

export function generalizedTime(dt: string): Date {
  let tz = dt.substring(14);
  if (tz != 'Z') {
    tz = tz.substring(0, 3) + ':'
      + (tz.length > 3 ? tz.substring(3, 5) : '00');
  }
  return new Date(dt.substring(0, 4) + '-'
    + dt.substring( 4,  6) + '-'
    + dt.substring( 6,  8) + 'T'
    + dt.substring( 8, 10) + ':'
    + dt.substring(10, 12) + ':'
    + dt.substring(12, 14) + tz);
}

let schema: LdapSchema;

export class RDN {
  readonly text: string;
  readonly attrName: string;
  readonly value: string;

  constructor(value: string) {
    this.text = value;
    const parts = value.split('=');
    this.attrName = parts[0].trim();
    this.value = parts[1].trim();
  }

  toString() { return this.text; }

  eq(other: RDN | undefined) {
    return other !== undefined
      && this.attr !== undefined
      && this.attr.eq(other.attr)
      && this.attr.matcher(this.value, other.value);
  }

  get attr() {
    return schema.attr(this.attrName);
  }
}

export class DN {
  readonly text: string;
  readonly rdn: RDN;
  readonly parent: DN | undefined;

  constructor(value: string) {
    this.text = value;
    const parts = value.split(',');
    this.rdn = new RDN(parts[0]);
    this.parent = parts.length == 1 ? undefined
      : new DN(value.slice(parts[0].length + 1));
  }

  toString() { return this.text; }

  eq(other: DN | undefined) : boolean {
    if (!other || !this.rdn.eq(other.rdn)) return false;
    if (!this.parent && !other.parent) return true;
    return !!this.parent && this.parent.eq(other.parent!);
  }
}

class Element {
  readonly oid?: string;
  readonly name?: string;
  readonly names?: string[];
  readonly sup?: string[];
}

export class ObjectClass extends Element {
  readonly desc?: string;
  readonly obsolete?: boolean;
  readonly may?: string[];
  readonly must?: string[];
  readonly kind?: string;

  constructor(json: object) {
    super();
    Object.assign(this, json);
  }

  get structural() { return this.kind == 'structural'; }

  // gather values from a field across all superclasses
  $collect(name: "must" | "may"): string[] {
    const attributes = [];
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    for (let oc: ObjectClass | undefined = this; oc; oc = oc.$super) {
      const attrs = oc[name];
      if (attrs) attributes.push(attrs);
    }

    const result = attributes.flat()
      .map(attr => schema.attr(attr))
      .map(obj => obj?.name)
      .filter(unique) as string[];
    result.sort();
    return result;
  }

  toString() { return this.name!; }

  get $super(): ObjectClass | undefined {
    const parent = Object.getPrototypeOf(this) as ObjectClass;
    return parent.sup ? parent : undefined;
  }
}

const matchRules: {[key: string]: (a: string, b: string) => boolean} = {
  // See: https://ldap.com/matching-rules/
  distinguishedNameMatch: (a: string, b: string) => new DN(a).eq(new DN(b)),
  caseIgnoreIA5Match: (a: string, b: string) => a.toLowerCase() == b.toLowerCase(),
  caseIgnoreMatch: (a: string, b: string) => a.toLowerCase() == b.toLowerCase(),
  // generalizedTimeMatch: ...
  integerMatch: (a: string, b: string) => +a == +b,
  numericStringMatch: (a: string, b: string) => +a == +b,
  octetStringMatch: (a: string, b: string) => a == b,
};

export class Attribute extends Element {
  desc?: string;
  equality?: string; // possibly null in JSON
  obsolete?: boolean;
  ordering?: string; // possibly null in JSON
  no_user_mod?: boolean;
  single_value?: boolean;
  substr?: string; // possibly null in JSON
  syntax?: string; // possibly null in JSON
  usage?: string;

  constructor(json: object) {
    super();

    // Hack alert: Wipe undefined attributes,
    // they are looked up via the prototype chain
    delete this.equality;
    delete this.ordering;
    delete this.substr;
    delete this.syntax;
    // End of hack

    Object.assign(this, Object.fromEntries(Object.entries(json)
      .filter(([_prop, value]) => value != null)));
  }

  toString() { return this.name!; }

  get matcher() {
    return (this.equality ? matchRules[this.equality] : undefined)
      || matchRules.octetStringMatch;
  }

  eq(other: Attribute | undefined) {
    return other && this.oid == other.oid;
  }

  get binary() {
    if (this.equality == 'octetStringMatch') return undefined;
    return this.$syntax?.not_human_readable;
  }

  get $syntax() { return schema.syntaxes.get(this.syntax!); }

  get $super() {
    const parent = Object.getPrototypeOf(this);
    return parent.sup ? parent : undefined;
  }
}

class Syntax {
  readonly oid?: string;
  readonly desc?: string;
  readonly not_human_readable?: boolean;

  constructor(json: object) {
    Object.assign(this, json);
  }

  toString() { return this.desc!; }
}

interface JsonSchema {
  attributes: object;
  objectClasses: object;
  syntaxes: object;
}

export class LdapSchema extends Object {
  readonly attributes: Array<Attribute>;
  readonly objectClasses: Map<string, ObjectClass>;
  readonly syntaxes: Map<string, Syntax>;
  readonly attributesByName: Map<string, Attribute>;

  constructor(json: JsonSchema) {
    super();
    this.syntaxes = new Map(Object.entries(json.syntaxes)
      .map(([oid, obj]) => [oid, new Syntax(obj)]));
    this.attributes = Object.values(json.attributes)
      .map(obj => new Attribute(obj));
    this.objectClasses = new Map(Object.entries(json.objectClasses)
      .map(([key, obj]) => [key.toLowerCase(), new ObjectClass(obj)]));
    this.buildPrototypeChain(this.objectClasses);
    
    this.attributesByName = new Map(this.attributes.flatMap(
      attr => (attr.names || []).map(name => [name.toLowerCase(), attr])));
    this.buildPrototypeChain(this.attributesByName);
    schema = this as LdapSchema;
  }

  private buildPrototypeChain(elements: Map<string, Element>): void {
    for (const element of elements.values()) {
      const key = element.sup ? element.sup[0] : undefined,
        parent = key ? elements.get(key.toLowerCase()) : undefined;
      if (parent) Object.setPrototypeOf(element, parent);
    }
  }

  attr(name: string | undefined) { return this.attributesByName.get(name?.toLowerCase() || ''); }
  oc(name: string | undefined) { return this.objectClasses.get(name?.toLowerCase() || ''); }

  search(q: string) {
    return this.attributes.filter(
      attr => attr.names?.some(name => name.toLowerCase().startsWith(q.toLowerCase())));
  }
}
