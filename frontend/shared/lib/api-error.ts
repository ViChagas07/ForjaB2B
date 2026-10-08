import { problemCode } from "@/infrastructure/http";

/**
 * Mapeia um erro de API (RFC 7807) para a chave de tradução da mensagem
 * amigável. Centralizado para que login/onboarding/company usem exatamente o
 * mesmo vocabulário de erro, sem duplicar switches.
 */

export function errorMessageKey(error: unknown): string {
  const code = problemCode(error);

  switch (code) {
    case "invalid_credentials":
      return "error.invalidCredentials";
    case "user_inactive":
      return "error.userInactive";
    case "invalid_refresh_token":
    case "invalid_token":
    case "token_expired":
      return "error.sessionExpired";
    case "invalid_cnpj":
      return "error.invalidCnpj";
    case "company_already_exists":
      return "error.companyAlreadyExists";
    case "cpf_already_exists":
      return "error.cpfAlreadyExists";
    case "company_not_found":
      return "error.companyNotFound";
    case "weak_password":
      return "error.weakPassword";
    case "validation_error":
      return "error.validation";
    case "network_error":
      return "error.network";
    case "product_not_found":
      return "error.productNotFound";
    case "product_not_sellable":
      return "error.productNotSellable";
    case "quantity_below_minimum":
      return "error.quantityBelowMinimum";
    case "insufficient_credit":
      return "error.insufficientCredit";
    case "credit_account_not_found":
      return "error.creditAccountNotFound";
    case "idempotency_conflict":
      return "error.idempotencyConflict";
    case "order_not_found":
      return "error.orderNotFound";
    case "empty_order":
      return "error.emptyOrder";
    case "invalid_order_state":
      return "error.invalidOrderState";
    default:
      return "error.generic";
  }
}
