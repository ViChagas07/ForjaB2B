/**
 * Contratos do contexto de pagamento (neutros, sem frameworks).
 *
 * O backend decide os meios disponíveis; o frontend nunca assume que o cartão
 * está habilitado. `checkout_url` é a página hospedada do Stripe para onde o
 * navegador deve ser redirecionado.
 */

import type { PaymentMethod } from "./ordering";

export interface PaymentMethods {
  methods: string[];
  stripe_enabled: boolean;
}

export interface InitiatePaymentInput {
  order_id: string;
  method: PaymentMethod;
  idempotency_key: string;
}

export interface Payment {
  id: string;
  order_id: string;
  method: string;
  amount: string;
  discount_amount: string;
  status: string;
  provider: string;
  provider_reference: string;
  checkout_url: string | null;
  created_at: string;
  paid_at: string | null;
}
