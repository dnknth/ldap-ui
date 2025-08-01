import { describe, expect, test } from "vitest";
import { LdapSchema, DN, Attribute, ObjectClass } from "./schema";
import json from "./test-schema.json";

const sut = new LdapSchema(json);

describe("LDAP schema items", () => {
  const dn1 = new DN("dc=foo,dc=bar"),
    dn2 = new DN("domainComponent=FOO,domainComponent=BAR"),
    dn3 = new DN("domainComponent=bar");

  describe("RDNs", () => {
    test("Attribute equality", () =>
      expect(dn1.rdn.attr).toEqual(sut.attr("domainComponent")));
    test("equality", () => expect(dn1.rdn.matches(dn2.rdn)).toBeTruthy());
    test("inequality", () => expect(dn1.rdn.matches(dn3.rdn)).toBeFalsy());
    test("part of DN", () => expect(dn1.rdn.matches(dn2.rdn)).toBeTruthy());
  });

  describe("DNs", () => {
    test("parent", () => expect(dn2.parent?.matches(dn3)).toBeTruthy());
    test("grandparent", () => expect(dn3.parent).toBeUndefined());
    test("nomalization", () => expect(dn2.toString()).toEqual("dc=foo,dc=bar"));
    test("matching", () => expect(dn1.matches(dn2)).toBeTruthy());
  });

  describe("DN search", () => {
    test("DN is subordinate of parent", () =>
      expect(dn1.isSubordinate(dn3)).toBeTruthy());
    test("DN is no subordinate of itself", () =>
      expect(dn1.isSubordinate(dn1)).toBeFalsy());
    test("DN is no subordinate of mismatched parent", () =>
      expect(dn3.isSubordinate(dn1)).toBeFalsy());
  });

  describe("Attributes", () => {
    const sn = sut.attr("sn"),
      name = sut.attr("name");

    test("SN is found in schema", () => expect(sn).toBeDefined());
    test("SN has name as prototype", () =>
      expect(Object.getPrototypeOf(sn)).toEqual(name));
    test("SN is an Attribute", () => expect(sn).toBeInstanceOf(Attribute));
    test("SN has no own equality", () =>
      expect(Object.getOwnPropertyNames(sn)).not.toContain("equality"));
    test("SN inherits equality from name", () =>
      expect(sn?.equality).toBeDefined());
    test("SN syntax resolution", () =>
      expect(sn?.$syntax?.toString()).toEqual("Directory String"));
    test("Search for SN", () => expect(sut.search("sur")).toEqual([sn]));
  });

  describe("ObjectClass inheritance", () => {
    const top = sut.oc("top"),
      dnsDomain = sut.oc("dnsDomain");

    function superClasses(cls?: ObjectClass): ObjectClass[] {
      const result = [];
      for (let oc = cls; oc; oc = Object.getPrototypeOf(oc)) {
        result.push(oc);
      }
      return result;
    }

    test("top is an ObjectClass", () =>
      expect(top).toBeInstanceOf(ObjectClass));
    test("dnsDomain inherits from top", () =>
      expect(superClasses(dnsDomain)).toContain(top));
  });
});
