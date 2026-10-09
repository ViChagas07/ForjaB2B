"use client";

import * as React from "react";

import { useRouter } from "@/i18n/navigation";
import { exchangeGoogleOAuthCode } from "@/shared/stores/auth-actions";

/**
 * Callback do OAuth Google (fluxo de redirect tradicional).
 *
 * O backend redireciona para cá APENAS com um exchange code opaco (`?code=...`).
 * Aqui o code é trocado por sessão (ou onboarding) via POST; nenhum token,
 * authorization code ou secret aparece na URL.
 */
export default function GoogleOAuthCallbackPage() {
  const router = useRouter();
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
      setFailed(true);
      return;
    }

    let cancelled = false;
    exchangeGoogleOAuthCode(code)
      .then((result) => {
        if (cancelled) return;
        if (result.status === "authenticated") {
          router.replace("/dashboard");
          router.refresh();
        } else {
          const params = new URLSearchParams();
          if (result.email) params.set("email", result.email);
          if (result.full_name) params.set("full_name", result.full_name);
          router.replace(`/onboarding?${params.toString()}`);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main id="main" className="container flex flex-1 items-center justify-center py-12">
      {failed ? (
        <p role="alert" className="text-sm text-destructive">
          Falha ao concluir o login com Google.
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">Concluindo autenticação…</p>
      )}
    </main>
  );
}
