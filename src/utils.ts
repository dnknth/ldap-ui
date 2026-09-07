import { search } from "@/generated";

/** Anything exposing an attribute search — LdapSchema satisfies this. */
interface AttributeSearchable {
  search(q: string): object[];
}

export function unique(
  element: unknown,
  index: number,
  array: Array<unknown>,
  keepEmpty = false,
): boolean {
  return (keepEmpty && element == "") || array.indexOf(element) == index;
}

export async function searchDns(q: string) {
  const response = await search({ path: { query: q } });
  return response.data ?? [];
}

export function searchAttrs(q: string, schema?: AttributeSearchable) {
  return (schema?.search(q) ?? []).map((a) => ({
    ...a,
  }));
}
