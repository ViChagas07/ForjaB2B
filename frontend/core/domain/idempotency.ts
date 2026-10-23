/**
 * Geracao e reutilizacao de chaves de idempotencia (header `Idempotency-Key`).
 *
 * A chave deve ser criada uma vez por tentativa de envio e reutilizada em
 * retentativas (timeout, falha de rede, duplo clique). O backend devolve a
 * resposta original com `Idempotent-Replayed: true` quando a chave e o payload
 * coincidem.
 */

export const IDEMPOTENCY_KEY_MIN_LENGTH = 16;
export const IDEMPOTENCY_KEY_MAX_LENGTH = 128;

const KEY_PATTERN = /^[A-Za-z0-9._~:/+=@-]{16,128}$/;

function fallbackUuid(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return fallbackUuid();
}

export function isValidIdempotencyKey(value: string): boolean {
  return KEY_PATTERN.test(value);
}

export interface IdempotencyKeyStore {
  /** Devolve a chave do escopo, criando-a na primeira chamada. */
  get(scope: string): string;
  /** Descarta a chave (ex.: novo checkout depois de concluido). */
  reset(scope?: string): void;
}

/**
 * Mapa escopo -> chave. Em checkout, o escopo pode ser o id do pedido, de modo
 * que a retentativa do pagamento reutilize a mesma chave.
 */
export function createIdempotencyKeyStore(): IdempotencyKeyStore {
  const keys = new Map<string, string>();
  return {
    get(scope: string): string {
      const existing = keys.get(scope);
      if (existing !== undefined) {
        return existing;
      }
      const key = newIdempotencyKey();
      keys.set(scope, key);
      return key;
    },
    reset(scope?: string): void {
      if (scope === undefined) {
        keys.clear();
        return;
      }
      keys.delete(scope);
    },
  };
}
