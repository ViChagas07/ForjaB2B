import type { HttpClient } from "@/core/application/ports/http-client";

import { FetchHttpClient } from "./api-client";
import { getApiBaseUrl } from "./config";

/**
 * Instância única do cliente HTTP (adapter). Consumida pelas camadas de
 * aplicação/features e pelos adapters de endpoint (auth-api, company-api);
 * nunca chamada diretamente de componentes visuais.
 */
export const apiClient: HttpClient = new FetchHttpClient(getApiBaseUrl());
