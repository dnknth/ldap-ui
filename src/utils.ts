export function unique(
  element: unknown,
  index: number,
  array: Array<unknown>,
): boolean {
  return array.indexOf(element) == index;
}
