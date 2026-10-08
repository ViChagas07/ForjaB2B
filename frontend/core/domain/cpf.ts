/**
 * Validação de CPF (11 dígitos + dígitos verificadores, módulo 11).
 *
 * O backend não recalcula os dígitos verificadores no onboarding (apenas
 * hasheia o valor normalizado para garantir "um CPF, uma conta"), então esta
 * validação client-side é uma camada extra de UX para evitar erros de digitação.
 * Todo CPF brasileiro válido possui dígitos verificadores corretos, logo a
 * validação não rejeita entradas legítimas.
 */

const NON_DIGITS = /\D/g;
const CPF_LENGTH = 11;

export function normalizeCpf(raw: string): string {
  return raw.replace(NON_DIGITS, "");
}

function checkDigit(base: string, factor: number): number {
  let total = 0;
  for (const char of base) {
    total += Number(char) * factor;
    factor -= 1;
  }
  const remainder = total % 11;
  return remainder < 2 ? 0 : 11 - remainder;
}

export function isValidCpf(raw: string): boolean {
  const digits = normalizeCpf(raw);
  if (digits.length !== CPF_LENGTH) {
    return false;
  }
  if (digits === (digits[0] ?? "").repeat(CPF_LENGTH)) {
    return false;
  }
  const base = digits.slice(0, 9);
  const first = checkDigit(base, 10);
  const second = checkDigit(base + String(first), 11);
  return digits === base + String(first) + String(second);
}
