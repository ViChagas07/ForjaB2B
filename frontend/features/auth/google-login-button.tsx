"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/shared/ui/button";

/**
 * Botão de login via Google OAuth tradicional (redirect para o backend).
 *
 * NÃO usa Google Identity Services (GIS) nem popup. Redireciona o navegador
 * para o endpoint OAuth do backend, que inicia o fluxo de autorização e, no
 * callback, reutiliza o mecanismo de sessão já existente (tokens -> store).
 *
 * Dependência registrada: o backend ainda não expõe endpoint OAuth; a URL é
 * configurável via `NEXT_PUBLIC_OAUTH_GOOGLE_URL`. Sem esse endpoint, o botão
 * fica oculto (não há fluxo utilizável para iniciar).
 */
export function GoogleLoginButton() {
  const t = useTranslations();
  const oauthUrl = process.env.NEXT_PUBLIC_OAUTH_GOOGLE_URL;

  if (!oauthUrl) {
    return null;
  }

  function handleClick() {
    window.location.assign(oauthUrl as string);
  }

  return (
    <Button type="button" variant="outline" className="w-full" onClick={handleClick}>
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4">
        <path
          fill="#4285F4"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
        />
        <path
          fill="#34A853"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
        />
        <path
          fill="#FBBC05"
          d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
        />
        <path
          fill="#EA4335"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52Z"
        />
      </svg>
      {t("auth.continueWithGoogle")}
    </Button>
  );
}
