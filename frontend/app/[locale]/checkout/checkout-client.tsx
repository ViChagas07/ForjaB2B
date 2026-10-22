"use client";

import { useRouter } from "@/i18n/navigation";
import type { PaymentMethod } from "@/core/domain/ordering";
import { CheckoutView } from "@/features/ordering";
import { useCart } from "@/features/cart";
import { useCreditAccount } from "@/features/credit";
import { useCreateOrder } from "@/features/ordering";
import { useInitiatePayment, usePaymentMethods } from "@/features/payment";

function newPaymentKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `pay-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function CheckoutClient() {
  const router = useRouter();
  const cartQuery = useCart();
  const creditQuery = useCreditAccount();
  const createOrderMutation = useCreateOrder();
  const methodsQuery = usePaymentMethods();
  const initiatePaymentMutation = useInitiatePayment();

  const stripeEnabled = methodsQuery.data?.stripe_enabled ?? false;
  const isPlacingOrder = createOrderMutation.isPending || initiatePaymentMutation.isPending;
  const orderError = createOrderMutation.error ?? initiatePaymentMutation.error;

  function handlePlaceOrder(paymentMethod: PaymentMethod, notes: string, idempotencyKey: string) {
    const cart = cartQuery.data;
    if (!cart) {
      return;
    }
    createOrderMutation.mutate(
      {
        items: cart.items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
        })),
        payment_method: paymentMethod,
        idempotency_key: idempotencyKey,
        notes: notes || null,
      },
      {
        onSuccess: (order) => {
          if (paymentMethod !== "CARD") {
            router.push(`/orders/${order.id}`);
            router.refresh();
            return;
          }
          // Cartao: cria a Checkout Session e envia o navegador ao Stripe.
          initiatePaymentMutation.mutate(
            {
              order_id: order.id,
              method: "CARD",
              idempotency_key: newPaymentKey(),
            },
            {
              onSuccess: (payment) => {
                if (payment.checkout_url) {
                  window.location.assign(payment.checkout_url);
                  return;
                }
                router.push(`/orders/${order.id}`);
              },
            },
          );
        },
      },
    );
  }

  // Enquanto carrega, mostra um fallback neutro (o componente trata erro/vazio).
  const cart = cartQuery.data ?? {
    cart_id: "",
    company_id: "",
    user_id: "",
    items: [],
    subtotal: "0.00",
  };

  return (
    <CheckoutView
      cart={cart}
      cartError={cartQuery.error}
      credit={creditQuery.data}
      stripeEnabled={stripeEnabled}
      isPlacingOrder={isPlacingOrder}
      orderError={orderError}
      onPlaceOrder={handlePlaceOrder}
    />
  );
}
