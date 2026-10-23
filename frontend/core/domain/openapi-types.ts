/**
 * Tipos gerados do contrato OpenAPI e verificacoes de compatibilidade.
 *
 * `api-schema.d.ts` e gerado por `openapi-typescript` a partir de
 * `docs/api/openapi.json` (job `openapi-contract`). Nao edite o arquivo gerado
 * manualmente: rode `npm run openapi:types`.
 *
 * Migracao gradual: os contratos escritos a mao (`Order`, `Payment`,
 * `AdminProductDetail`) continuam sendo a fonte usada pela UI. As verificacoes
 * abaixo garantem, em tempo de compilacao, que todo campo publicado no
 * OpenAPI existe no tipo manual. Campos novos podem ser adotados
 * incrementalmente a partir de `ApiSchemas`.
 */

import type { components, operations, paths } from "./api-schema";
import type { AdminProductDetail } from "./catalog";
import type { Order, OrderItem } from "./ordering";
import type { Payment } from "./payment";

export type ApiPaths = paths;
export type ApiOperations = operations;
export type ApiSchemas = components["schemas"];
export type ApiOrderResponse = ApiSchemas["OrderResponse"];
export type ApiPaymentResponse = ApiSchemas["PaymentResponse"];
export type ApiAdminProductDetail = ApiSchemas["ProductAdminDetail"];
export type ApiProblemDetails = ApiSchemas["ProblemDetails"];

type Assert<T extends true> = T;
type KeysAreSubset<A, B> = [keyof A] extends [keyof B] ? true : false;

/**
 * Guardas de drift: falham o `tsc` se o OpenAPI remover/renomear um campo que
 * a UI consome. O legado `fallback` e local (nao publicado no esquema) e por
 * isso e omitido.
 */
export type ContractChecks = [
  Assert<KeysAreSubset<ApiOrderResponse, Omit<Order, "fallback">>>,
  Assert<KeysAreSubset<ApiOrderResponse["items"][number], Omit<OrderItem, "fallback">>>,
  Assert<KeysAreSubset<Payment, ApiPaymentResponse>>,
  Assert<KeysAreSubset<ApiAdminProductDetail, AdminProductDetail>>,
];
