import type { Metadata } from "next";
import { XCircle } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.paymentCancelTitle") };
}

export default async function CheckoutCancelPage() {
  const t = await getTranslations();

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <Card className="mx-auto w-full max-w-lg rounded-3xl">
          <CardContent className="flex flex-col items-center gap-4 p-8 text-center sm:p-10">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
              <XCircle aria-hidden="true" className="h-8 w-8" />
            </span>
            <h1 className="text-2xl font-black tracking-tight">
              {t("ordering.paymentCancelTitle")}
            </h1>
            <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
              {t("ordering.paymentCancelDescription")}
            </p>
            <Button asChild className="mt-2 rounded-xl">
              <Link href="/cart">{t("ordering.backToCart")}</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
      <SiteFooter />
    </>
  );
}
