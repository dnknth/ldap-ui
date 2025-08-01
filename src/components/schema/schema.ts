import type { Schema } from "../../generated/types.gen";

function unique(
  element: unknown,
  index: number,
  array: Array<unknown>,
): boolean {
  return array.indexOf(element) == index;
}

export function generalizedTime(dt: string): Date {
  let tz = dt.substring(14);
  if (tz != "Z") {
    tz = tz.substring(0, 3) + ":" + (tz.length > 3 ? tz.substring(3, 5) : "00");
  }
  return new Date(
    dt.substring(0, 4) +
      "-" +
      dt.substring(4, 6) +
      "-" +
      dt.substring(6, 8) +
      "T" +
      dt.substring(8, 10) +
      ":" +
      dt.substring(10, 12) +
      ":" +
      dt.substring(12, 14) +
      tz,
  );
}

let schema: LdapSchema;

export class RDN {
  readonly attr: Attribute;
  readonly value: string;

  constructor(value: string) {
    const parts = value.split("=");
    this.attr = schema.attr(parts[0].trim())!;
    this.value = parts[1].trim();
  }

  /// Normalize the RDN representaion
  toString(): string {
    return this.attr.name + "=" + this.attr.normalizer(this.value);
  }

  matches(other?: RDN): boolean {
    return other !== undefined && this.toString() == other.toString();
  }
}

export class DN {
  readonly rdn: RDN;
  readonly parent?: DN;

  constructor(value: string) {
    const parts = value.split(",");
    this.rdn = new RDN(parts[0]);
    this.parent =
      parts.length == 1 ? undefined : new DN(value.slice(parts[0].length + 1));
  }

  /// Normalize the DN representaion
  toString(): string {
    const rdnString = this.rdn.toString();
    return this.parent ? rdnString + "," + this.parent.toString() : rdnString;
  }

  get level(): number {
    return this.parent ? this.parent.level + 1 : 0;
  }

  // See: https://ldapwiki.com/wiki/Wiki.jsp?page=DistinguishedNameMatch
  matches(other?: DN): boolean {
    if (!other || !this.rdn.matches(other.rdn)) return false;
    if (!this.parent && !other.parent) return true;
    return !!this.parent && this.parent.matches(other.parent!);
  }

  isSubordinate(ancestor: DN): boolean {
    let dn: DN | undefined = this.parent;
    while (dn) {
      if (dn.matches(ancestor)) return true;
      dn = dn.parent;
    }
    return false;
  }

  parents(base?: DN): DN[] {
    const dns = [];
    for (let dn = this.parent; dn; dn = dn.parent) {
      dns.push(dn);
      if (!dn.parent || dn.matches(base)) break;
    }
    return dns;
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

  get structural(): boolean {
    return this.kind == "structural";
  }
  get aux(): boolean {
    return this.kind == "auxiliary";
  }

  // gather values from a field across all superclasses
  $collect(name: "must" | "may"): string[] {
    const attributes = [];
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    for (let oc: ObjectClass | undefined = this; oc; oc = oc.$super) {
      const attrs = oc[name];
      if (attrs) attributes.push(attrs);
    }

    const result = attributes
      .flat()
      .map((attr) => schema.attr(attr))
      .map((obj) => obj?.name)
      .filter(unique) as string[];
    result.sort();
    return result;
  }

  toString(): string {
    return this.name!;
  }

  get $super(): ObjectClass | undefined {
    const parent = Object.getPrototypeOf(this) as ObjectClass;
    return parent.sup ? parent : undefined;
  }
}

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

  normalizers: { [key: string]: (a: string) => string | number } = {
    // See: https://ldap.com/matching-rules/
    distinguishedNameMatch: (a) => new DN(a).toString(),
    caseIgnoreIA5Match: (a) => a.toLowerCase(),
    caseIgnoreMatch: (a) => a.toLowerCase(),
    generalizedTimeMatch: (a) => generalizedTime(a).toISOString(),
    integerMatch: (a) => +a,
    numericStringMatch: (a) => +a,
    octetStringMatch: (a) => a,
  };

  constructor(json: object) {
    super();

    // Hack alert: Wipe undefined attributes,
    // they are looked up via the prototype chain
    delete this.equality;
    delete this.ordering;
    delete this.substr;
    delete this.syntax;
    // End of hack

    Object.assign(
      this,
      Object.fromEntries(
        Object.entries(json).filter(([_prop, value]) => value != null),
      ),
    );
  }

  toString(): string {
    return this.name!;
  }

  get normalizer(): (a: string) => string | number {
    return (
      this.normalizers[this.equality || "octetStringMatch"] ||
      this.normalizers.octetStringMatch
    );
  }

  get binary(): boolean | undefined {
    if (this.equality == "octetStringMatch") return undefined;
    return !!this.$syntax?.not_human_readable;
  }

  get $syntax(): Syntax | undefined {
    if (!this.syntax) return undefined;
    return schema.syntaxes.get(this.syntax);
  }

  get $super(): Attribute | undefined {
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

  toString(): string {
    return this.desc!;
  }
}

export class LdapSchema {
  readonly attributes: Array<Attribute>;
  readonly objectClasses: Map<string, ObjectClass>;
  readonly syntaxes: Map<string, Syntax>;
  readonly attributesByName: Map<string, Attribute>;

  constructor(json: Schema) {
    this.syntaxes = new Map(
      Object.entries(json.syntaxes).map(([oid, obj]) => [oid, new Syntax(obj)]),
    );
    this.attributes = Object.values(json.attributes).map(
      (obj) => new Attribute(obj),
    );
    this.objectClasses = new Map(
      Object.entries(json.objectClasses).map(([key, obj]) => [
        key.toLowerCase(),
        new ObjectClass(obj),
      ]),
    );
    this.buildPrototypeChain(this.objectClasses);

    this.attributesByName = new Map(
      this.attributes.flatMap((attr) =>
        (attr.names || []).map((name) => [name.toLowerCase(), attr]),
      ),
    );
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

  attr(name?: string): Attribute | undefined {
    return this.attributesByName.get(name?.toLowerCase() || "");
  }
  oc(name?: string): ObjectClass | undefined {
    return this.objectClasses.get(name?.toLowerCase() || "");
  }

  search(q: string): Attribute[] {
    return this.attributes.filter((attr) =>
      attr.names?.some((name) =>
        name.toLowerCase().startsWith(q.toLowerCase()),
      ),
    );
  }
}
