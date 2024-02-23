import { describe, expect, test } from 'vitest';
import { LdapSchema, DN, Attribute, ObjectClass } from './schema';
import json from './test-schema.json';

const sut = new LdapSchema(json);

describe('LDAP schema items', () => {
  describe('DNs and RDNs', () => {
    const 
      dn1 = new DN('dc=foo,dc=bar'), rdn1 = dn1.rdn,
      dn2 = new DN('domainComponent=FOO,domainComponent=BAR'), rdn2 = dn2.rdn,
      dn3 = new DN('domainComponent=bar'), rdn3 = dn3.rdn;

    test('Test RDN attribute equality', () => 
      expect(rdn1.attr).toEqual(sut.attr('domainComponent')));

    test('Test RDN equality', () => 
      expect(rdn1.eq(rdn2)).toBeTruthy());

    test('Test RDN inequality', () => 
      expect(rdn1.eq(rdn3)).toBeFalsy());

    test('Test RDN part of DN', () =>
      expect(dn1.rdn.eq(rdn2)).toBeTruthy());

    test('Test DN parent', () =>
      expect(dn2.parent?.eq(dn3)).toBeTruthy());

    test('Test DN grandparent', () =>
      expect(dn3.parent).toBeUndefined());

    test('Test DN equality', () =>
      expect(dn1.eq(dn2)).toBeTruthy());
  });

  describe('Attributes', () => {
    const sn = sut.attr('sn'),
      name = sut.attr('name');

    test('SN is found in schema', () =>
      expect(sn).toBeDefined());

    test('SN has name as prototype', () =>
      expect(Object.getPrototypeOf(sn)).toEqual(name));

    test('SN is an Attribute', () =>
      expect(sn).toBeInstanceOf(Attribute));

    test('SN has no own equality', () =>
      expect(Object.getOwnPropertyNames(sn)).not.toContain('equality'));

    test('SN inherits equality from name', () =>
      expect(sn?.equality).toBeDefined());

    test('SN syntax resolution', () =>
      expect(sn?.$syntax?.toString()).toEqual('Directory String'));

    test('Search for SN', () =>
      expect(sut.search('sur')).toEqual([sn]));
  });

  describe('ObjectClass inheritance', () => {
    const top = sut.oc('top'),
      dnsDomain = sut.oc('dnsDomain');

    function superClasses(cls: ObjectClass | undefined) : ObjectClass[] {
      const result = [];
      for (let oc = cls; oc; oc = Object.getPrototypeOf(oc)) {
        result.push(oc);
      }
      return result;
    }

    test('top is an ObjectClass', () =>
      expect(top).toBeInstanceOf(ObjectClass));

    test('dnsDomain inherits from top', () =>
      expect(superClasses(dnsDomain)).toContain(top));
  });
});
