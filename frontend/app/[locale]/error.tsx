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
      <div className="rounded-2xl border border-border bg-card px-8 py-12 shadow-sm">
        <h1 className="text-2xl font-black tracking-tight">{t("errorTitle")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("errorDescription")}</p>
        <Button className="mt-6 rounded-xl" onClick={reset}>
          {t("errorRetry")}
        </Button>
      </div>
    </main>
  );
}
