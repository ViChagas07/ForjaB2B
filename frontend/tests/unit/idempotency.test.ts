import { describe, expect, it } from "vitest";

import {
  createIdempotencyKeyStore,
  isValidIdempotencyKey,
  newIdempotencyKey,
} from "@/core/domain/idempotency";

describe("newIdempotencyKey", () => {
  it("gera chave valida de 16 a 128 caracteres", () => {
    const key = newIdempotencyKey();

    expect(key.length).toBeGreaterThanOrEqual(16);
    expect(key.length).toBeLessThanOrEqual(128);
    expect(isValidIdempotencyKey(key)).toBe(true);
  });

  it("rejeita chave curta ou com espacos", () => {
    expect(isValidIdempotencyKey("curta")).toBe(false);
    expect(isValidIdempotencyKey("chave com espaco 1234567890")).toBe(false);
  });
});

describe("createIdempotencyKeyStore", () => {
  it("reutiliza a mesma chave para o mesmo escopo (retentativa)", () => {
    const store = createIdempotencyKeyStore();

    const first = store.get("order-1");
    const second = store.get("order-1");

    expect(second).toBe(first);
  });

  it("gera chaves distintas por escopo", () => {
    const store = createIdempotencyKeyStore();

    expect(store.get("order-1")).not.toBe(store.get("order-2"));
  });

  it("reset limpa o escopo e cria nova chave", () => {
    const store = createIdempotencyKeyStore();
    const first = store.get("order-1");

    store.reset("order-1");

    expect(store.get("order-1")).not.toBe(first);
  });
});
