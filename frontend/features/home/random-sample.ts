export function randomSample<T>(
  items: readonly T[],
  count: number,
  random: () => number = Math.random,
): T[] {
  if (count <= 0 || items.length === 0) {
    return [];
  }
  if (items.length <= count) {
    return [...items];
  }
  const pool = [...items];
  const picked: T[] = [];
  while (picked.length < count && pool.length > 0) {
    const index = Math.floor(random() * pool.length);
    picked.push(pool.splice(index, 1)[0] as T);
  }
  return picked;
}
