import { describe, expect, it } from "vitest";

import { randomSample } from "@/features/home/random-sample";

function seededRandom(values: number[]) {
  let index = 0;
  return () => values[index++ % values.length] as number;
}

describe("amostra aleatória de produtos", () => {
  it("devolve exatamente a quantidade pedida, sem repetição", () => {
    const items = ["a", "b", "c", "d", "e", "f"];
    const picked = randomSample(items, 4, seededRandom([0, 0.5, 0.2, 0.9]));
    expect(picked).toHaveLength(4);
    expect(new Set(picked).size).toBe(4);
    for (const item of picked) {
      expect(items).toContain(item);
    }
  });

  it("com pool menor que a quantidade, devolve o pool inteiro", () => {
    const items = ["a", "b"];
    expect(randomSample(items, 4, seededRandom([0.1]))).toEqual(["a", "b"]);
  });

  it("com pool vazio ou quantidade zero, devolve lista vazia", () => {
    expect(randomSample([], 3, seededRandom([0.5]))).toEqual([]);
    expect(randomSample(["a"], 0, seededRandom([0.5]))).toEqual([]);
  });

  it("não muta a lista original", () => {
    const items = ["a", "b", "c"];
    randomSample(items, 2, seededRandom([0.9, 0.1]));
    expect(items).toEqual(["a", "b", "c"]);
  });
});
