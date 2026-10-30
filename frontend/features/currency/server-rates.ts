import { normalizeFxRatesPayload, type FxRatesSnapshot } from "@/core/domain/currency";
import { getApiBaseUrl } from "@/infrastructure/http/config";

/**
 * Busca das taxas no SERVIDOR (layout), com o cache de dados do Next.
 *
 * - endpoint público fixo, sem query/cookie/Authorization na URL;
 * - `revalidate` de 12h e tag única; nenhum polling;
 * - qualquer falha (rede, timeout, 5xx, payload inválido) devolve `null` e a
 *   aplicação segue em BRL sem derrubar a renderização.
 *
 * Este módulo NUNCA deve ser importado por Client Component.
 */

export const FX_RATES_REVALIDATE_SECONDS = 12 * 60 * 60;
export const FX_RATES_TAG = "fx:rates";
const FX_TIMEOUT_MS = 5_000;

function fxRatesUrl(): string | null {
  const baseUrl = getApiBaseUrl();
  if (!/^https?:\/\//i.test(baseUrl)) return null;
  return `${baseUrl.replace(/\/+$/, "")}/fx/rates`;
}

export async function getFxRatesForServer(): Promise<FxRatesSnapshot | null> {
  const url = fxRatesUrl();
  if (url === null) return null;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json, application/problem+json" },
      credentials: "omit",
      signal: AbortSignal.timeout(FX_TIMEOUT_MS),
      next: { revalidate: FX_RATES_REVALIDATE_SECONDS, tags: [FX_RATES_TAG] },
    });

    if (!response.ok) {
      console.warn(`[fx] taxas indisponiveis (HTTP ${response.status}); seguindo em BRL`);
      return null;
    }

    const payload: unknown = await response.json();
    return normalizeFxRatesPayload(payload);
  } catch (error) {
    console.warn(
      "[fx] falha ao buscar taxas; seguindo em BRL:",
      error instanceof Error ? error.message : error,
    );
    return null;
  }
}
