"use client";

import * as React from "react";

import { accountApi } from "@/infrastructure/http";
import { useCurrency } from "@/shared/components/currency-provider";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Persiste a moeda de EXIBICAO no perfil quando o usuario esta autenticado.
 *
 * O provider atualiza estado e cookie imediatamente; esta sincronizacao e
 * best-effort e nunca bloqueia a UI. Em caso de falha de rede/401, o cookie
 * continua valendo para o SSR e a proxima troca tenta novamente.
 */
export function CurrencyProfileSync() {
  const { currency } = useCurrency();
  const authStatus = useAuthStore((state) => state.status);
  const previous = React.useRef(currency);

  React.useEffect(() => {
    if (previous.current === currency) return;
    previous.current = currency;
    if (authStatus !== "authenticated") return;

    const accessToken = useAuthStore.getState().session?.access_token;
    if (!accessToken) return;

    void accountApi.updatePreferences(accessToken, currency).catch(() => undefined);
  }, [authStatus, currency]);

  return null;
}
