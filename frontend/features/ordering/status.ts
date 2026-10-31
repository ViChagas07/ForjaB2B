import type { OrderStatus } from "@/core/domain/ordering";

/** Chave i18n do rótulo de status exibido em pedidos e no painel. */
export function orderStatusLabelKey(status: OrderStatus | string): string {
  switch (status) {
    case "RECEIVED":
      return "ordering.statusReceived";
    case "CREDIT_REVIEW":
      return "ordering.statusCreditReview";
    case "PAID":
      return "ordering.statusPaid";
    case "INVOICED":
      return "ordering.statusInvoiced";
    case "IN_TRANSIT":
      return "ordering.statusInTransit";
    case "DELIVERED":
      return "ordering.statusDelivered";
    case "CANCELLED":
      return "ordering.statusCancelled";
    case "CREDIT_REJECTED":
      return "ordering.statusCreditRejected";
    default:
      return "";
  }
}

export type DeliveryStage = 0 | 1 | 2 | 3;

/**
 * Converte o status transacional no estágio visível da rota de entrega:
 * preparando -> transportadora -> à caminho -> entregue.
 *
 * Pedidos cancelados ou com crédito recusado não entram na rota.
 */
export function deliveryStage(status: OrderStatus | string): DeliveryStage | null {
  switch (status) {
    case "RECEIVED":
    case "CREDIT_REVIEW":
    case "PAID":
      return 0;
    case "INVOICED":
      return 1;
    case "IN_TRANSIT":
      return 2;
    case "DELIVERED":
      return 3;
    default:
      return null;
  }
}

export function isCancelledStatus(status: OrderStatus | string): boolean {
  return status === "CANCELLED" || status === "CREDIT_REJECTED";
}
