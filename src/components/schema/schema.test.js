import { describe, expect, test } from 'vitest';
import { LdapSchema } from './schema.js';
import jsonSchema from './test-schema.json';

const schema = new LdapSchema(jsonSchema);


describe('LDAP schema items', () => {
  describe('DNs and RDNs', () => {
    const 
      dn1 = new schema.DN('dc=foo,dc=bar'), rdn1 = dn1.rdn,
      dn2 = new schema.DN('domainComponent=FOO,domainComponent=BAR'), rdn2 = dn2.rdn,
      dn3 = new schema.DN('domainComponent=bar'), rdn3 = dn3.rdn;

    test('Test RDN attribute equality', () => 
      expect(rdn1.attr).toEqual(schema.attr('domainComponent')));

    test('Test RDN equality', () => 
      expect(rdn1.eq(rdn2)).toBeTruthy());

    test('Test RDN inequality', () => 
      expect(rdn1.eq(rdn3)).toBeFalsy());

    test('Test RDN part of DN', () =>
      expect(dn1.rdn.eq(rdn2)).toBeTruthy());

    test('Test DN parent', () =>
      expect(dn2.parent.eq(dn3)).toBeTruthy());

    test('Test DN grandparent', () =>
      expect(dn3.parent).toBeUndefined());

    test('Test DN equality', () =>
      expect(dn1.eq(dn2)).toBeTruthy());
  });

  describe('Attributes', () => {
    const sn = schema.attr('sn'),
      name = schema.attr('name');

    test('SN is found in schema', () =>
      expect(sn).toBeDefined());

    test('SN has name as prototype', () =>
      expect(Object.getPrototypeOf(sn)).toEqual(name));

    test('SN is an Attribute', () =>
      expect(sn).toBeInstanceOf(schema.Attribute));

    test('SN has no own equality', () =>
      expect(Object.getOwnPropertyNames(sn)).not.toContain('equality'));

    test('SN inherits equality from name', () =>
      expect(sn.equality).toBeDefined());

    test('SN syntax resolution', () =>
      expect(sn.$syntax.toString()).toEqual('Directory String'));
  });

  describe('ObjectClass inheritance', () => {
    const top = schema.oc('top'),
      dnsDomain = schema.oc('dnsDomain');

    function superClasses(cls) {
      let result = [];
      for (let oc = cls; oc; oc = Object.getPrototypeOf(oc)) {
        result.push(oc);
      }
      return result;
    }

    test('top is an ObjectClass', () =>
      expect(top).toBeInstanceOf(schema.ObjectClass));

    test('dnsDomain inherits from top', () =>
      expect(superClasses(dnsDomain)).toContain(top));
  });
});
