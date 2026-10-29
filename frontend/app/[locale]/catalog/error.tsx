"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/shared/ui/button";

export default function CatalogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations();

  useEffect(() => {
    // O backend pode estar acordando; o digest correlaciona com o log do Next.
    console.error(error);
  }, [error]);

  return (
    <main id="main" className="container flex flex-1 flex-col items-center justify-center py-24">
      <div className="max-w-lg rounded-2xl border border-border bg-card px-8 py-12 text-center shadow-sm">
        <h1 className="text-2xl font-black tracking-tight">{t("catalog.loadError")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("errorDescription")}</p>
        <Button className="mt-6 rounded-xl" onClick={reset}>
          {t("errorRetry")}
        </Button>
      </div>
    </main>
  );
}
