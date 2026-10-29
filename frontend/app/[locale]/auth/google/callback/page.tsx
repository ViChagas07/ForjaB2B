"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { errorMessageKey, oauthErrorMessageKey } from "@/shared/lib/api-error";
import { exchangeGoogleOAuthCode } from "@/shared/stores/auth-actions";

/**
 * Callback do OAuth Google (fluxo de redirect tradicional).
 *
 * O backend redireciona para cá APENAS com um exchange code opaco (`?code=...`).
 * Aqui o code é trocado por sessão (ou pelo aviso de cadastro obrigatório) via
 * POST; nenhum token, authorization code ou secret aparece na URL.
 */
export default function GoogleOAuthCallbackPage() {
  const router = useRouter();
  const t = useTranslations();
  const [error, setError] = React.useState<string | null>(null);
  const started = React.useRef(false);

  React.useEffect(() => {
    // O exchange code é de uso único: evita consumi-lo duas vezes no
    // StrictMode do React em desenvolvimento.
    if (started.current) return;
    started.current = true;

    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    if (oauthError) {
      setError(t(oauthErrorMessageKey(oauthError)));
      return;
    }
    const code = params.get("code");
    if (!code) {
      setError(t("auth.googleCallbackError"));
      return;
    }

    let cancelled = false;
    exchangeGoogleOAuthCode(code)
      .then((result) => {
        if (cancelled) return;
        if (result.status === "authenticated") {
          router.replace("/dashboard");
          router.refresh();
          return;
        }
        const params = new URLSearchParams({ tipo: "cpf", origem: "google" });
        if (result.email) params.set("email", result.email);
        if (result.full_name) params.set("full_name", result.full_name);
        router.replace(`/onboarding?${params.toString()}`);
      })
      .catch((cause) => {
        if (!cancelled) setError(t(errorMessageKey(cause)));
      });

    return () => {
      cancelled = true;
    };
  }, [router, t]);

  return (
    <main id="main" className="container flex flex-1 items-center justify-center py-12">
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">{t("auth.googleCallbackLoading")}</p>
      )}
    </main>
  );
}
