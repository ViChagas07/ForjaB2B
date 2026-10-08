/**
 * Validação de CNPJ (espelha o algoritmo do backend `companies.domain.cnpj`).
 *
 * Não basta uma regex de formato: os dois dígitos verificadores são
 * recalculados a partir dos 12 primeiros dígitos (módulo 11). Sequências
 * repetidas (ex.: 00000000000000) são rejeitadas. O valor enviado ao backend
 * é sempre normalizado para 14 dígitos.
 */

const NON_DIGITS = /\D/g;
const CNPJ_LENGTH = 14;

const FIRST_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] as const;
const SECOND_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] as const;

export function normalizeCnpj(raw: string): string {
  return raw.replace(NON_DIGITS, "");
}

function checkDigit(base: string, weights: readonly number[]): string {
  let total = 0;
  for (let i = 0; i < weights.length; i += 1) {
    const weight = weights[i] ?? 0;
    total += Number(base[i]) * weight;
  }
  const remainder = total % 11;
  return remainder < 2 ? "0" : String(11 - remainder);
}

export function isValidCnpj(raw: string): boolean {
  const digits = normalizeCnpj(raw);
  if (digits.length !== CNPJ_LENGTH) {
    return false;
  }
  if (digits === (digits[0] ?? "").repeat(CNPJ_LENGTH)) {
    return false;
  }
  const first = checkDigit(digits.slice(0, 12), FIRST_WEIGHTS);
  const second = checkDigit(digits.slice(0, 12) + first, SECOND_WEIGHTS);
  return digits === digits.slice(0, 12) + first + second;
}
