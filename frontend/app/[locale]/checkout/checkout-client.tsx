"use client";

import * as React from "react";

import { useRouter } from "@/i18n/navigation";
import { createIdempotencyKeyStore } from "@/core/domain/idempotency";
import type { PaymentMethod } from "@/core/domain/ordering";
import { CheckoutView } from "@/features/ordering";
import { useCart } from "@/features/cart";
import { useCreditAccount } from "@/features/credit";
import { useCreateOrder } from "@/features/ordering";
import { useInitiatePayment, usePaymentMethods } from "@/features/payment";

interface CheckoutClientProps {
  selectedProductIds: string[] | null;
}

export function CheckoutClient({ selectedProductIds }: CheckoutClientProps) {
  const router = useRouter();
  const cartQuery = useCart();
  const creditQuery = useCreditAccount();
  const createOrderMutation = useCreateOrder();
  const methodsQuery = usePaymentMethods();
  const initiatePaymentMutation = useInitiatePayment();
  // Uma chave de pagamento por pedido: se a criacao da sessao falhar e o
  // usuario tentar de novo, a mesma chave e reutilizada.
  const paymentKeys = React.useRef(createIdempotencyKeyStore());

  const stripeEnabled = methodsQuery.data?.stripe_enabled ?? false;
  const isPlacingOrder = createOrderMutation.isPending || initiatePaymentMutation.isPending;
  const orderError = createOrderMutation.error ?? initiatePaymentMutation.error;

  function handlePlaceOrder(
    paymentMethod: PaymentMethod,
    notes: string,
    idempotencyKey: string,
    couponCode: string | null,
  ) {
    const cart = cartQuery.data;
    if (!cart) {
      return;
    }
    const selected = selectedProductIds ? new Set(selectedProductIds) : null;
    const items = selected
      ? cart.items.filter((item) => selected.has(item.product_id))
      : cart.items;
    if (items.length === 0) {
      return;
    }
    createOrderMutation.mutate(
      {
        items: items.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
        })),
        payment_method: paymentMethod,
        idempotency_key: idempotencyKey,
        notes: notes || null,
        coupon_code: couponCode,
      },
      {
        onSuccess: (order) => {
          if (paymentMethod === "BOLETO") {
            // Boleto faturado: fatura/credito sao tratados no fluxo do pedido.
            router.push(`/orders/${order.id}`);
            router.refresh();
            return;
          }
          // Cartao/PIX: cria a sessao no Stripe e envia o navegador ao checkout.
          initiatePaymentMutation.mutate(
            {
              order_id: order.id,
              method: paymentMethod,
              idempotency_key: paymentKeys.current.get(order.id),
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
  const cart = React.useMemo(() => {
    const base = cartQuery.data ?? {
      cart_id: "",
      company_id: "",
      user_id: "",
      items: [],
      subtotal: "0.00",
    };
    if (!selectedProductIds || !cartQuery.data) {
      return base;
    }
    const selected = new Set(selectedProductIds);
    const items = base.items.filter((item) => selected.has(item.product_id));
    const subtotal = items.reduce((sum, item) => sum + Number(item.line_total), 0);
    const listSubtotal = items.reduce(
      (sum, item) => sum + Number(item.list_line_total ?? item.line_total),
      0,
    );
    return {
      ...base,
      items,
      subtotal: subtotal.toFixed(2),
      list_subtotal: listSubtotal.toFixed(2),
      cnpj_discount_total: (listSubtotal - subtotal).toFixed(2),
    };
  }, [cartQuery.data, selectedProductIds]);

  return (
    <CheckoutView
      cart={cart}
      cartError={cartQuery.error}
      credit={creditQuery.data}
      stripeEnabled={stripeEnabled}
      isPlacingOrder={isPlacingOrder}
      orderError={orderError}
      selectedProductIds={selectedProductIds}
      onPlaceOrder={handlePlaceOrder}
    />
  );
}
