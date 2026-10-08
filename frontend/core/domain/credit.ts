/**
 * Contratos do contexto de crédito (neutros, sem frameworks).
 *
 * Somente leitura no frontend: reserva/liberação são internas ao backend.
 */

export interface CreditAccount {
  company_id: string;
  credit_limit: string;
  used: string;
  available: string;
  currency: string;
}

export interface CreditEntry {
  id: string;
  entry_type: string;
  amount: string;
  reference_type: string | null;
  reference_id: string | null;
  description: string | null;
  created_at: string;
}
