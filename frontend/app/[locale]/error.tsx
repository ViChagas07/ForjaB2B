"use client";

import { useTranslations } from "next-intl";
import * as React from "react";

import { Button } from "@/shared/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations();

  React.useEffect(() => {
    // Log estruturado do erro no cliente. O `digest` permite correlacionar
    // com o log do servidor (Next.js).
    console.error(error);
  }, [error]);

  return (
    <main className="container flex flex-1 flex-col items-center justify-center gap-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">{t("errorTitle")}</h1>
      <p className="text-muted-foreground">{t("errorDescription")}</p>
      <Button onClick={reset}>{t("errorRetry")}</Button>
    </main>
  );
}
