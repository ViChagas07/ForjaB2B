"use client";

import { useRouter } from "@/i18n/navigation";
import type { PaymentMethod } from "@/core/domain/ordering";
import { CheckoutView } from "@/features/ordering";
import { useCart } from "@/features/cart";
import { useCreditAccount } from "@/features/credit";
import { useCreateOrder } from "@/features/ordering";

export function CheckoutClient() {
  const router = useRouter();
  const cartQuery = useCart();
  const creditQuery = useCreditAccount();
  const createOrderMutation = useCreateOrder();

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
          router.push(`/orders/${order.id}`);
          router.refresh();
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
      isPlacingOrder={createOrderMutation.isPending}
      orderError={createOrderMutation.error}
      onPlaceOrder={handlePlaceOrder}
    />
  );
}
