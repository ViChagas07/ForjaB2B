export { DomainError } from "./errors";
export { ok, err, isOk, isErr, mapResult } from "./result";
export type { Result } from "./result";

export { ROLES } from "./auth";
export type { Role, UserProfile, AuthSession, AuthTokens } from "./auth";
export { COMPANY_STATUSES } from "./company";
export type {
  CompanyStatus,
  Company,
  RegisterCompanyInput,
  RegisterCompanyResult,
} from "./company";
export { normalizeCnpj, isValidCnpj } from "./cnpj";
export { normalizeCpf, isValidCpf } from "./cpf";

export { PRODUCT_STATUSES, CA_STATUSES, SORT_FIELDS, SORT_ORDERS } from "./catalog";
export type {
  ProductStatus,
  CaStatus,
  SortField,
  SortOrder,
  CategoryRef,
  Category,
  BrandRef,
  ProductSummary,
  ProductDetail,
  ProductListResponse,
  ProductListQuery,
} from "./catalog";
export type { Cart, CartItem, AddCartItemInput, UpdateCartItemInput } from "./cart";
export { PAYMENT_METHODS, ORDER_STATUSES } from "./ordering";
export type {
  PaymentMethod,
  OrderStatus,
  Order,
  OrderItem,
  OrderItemInput,
  CreateOrderInput,
} from "./ordering";
export type { CreditAccount, CreditEntry } from "./credit";
