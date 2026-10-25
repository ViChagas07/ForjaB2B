import type { Metadata } from "next";
import { CheckCircle2 } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

interface CheckoutSuccessPageProps {
  searchParams: { order_id?: string };
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.paymentSuccessTitle") };
}

export default async function CheckoutSuccessPage({ searchParams }: CheckoutSuccessPageProps) {
  const t = await getTranslations();
  const orderId = searchParams.order_id;

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <Card className="mx-auto w-full max-w-lg rounded-3xl">
          <CardContent className="flex flex-col items-center gap-4 p-8 text-center sm:p-10">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-success/10 text-success">
              <CheckCircle2 aria-hidden="true" className="h-8 w-8" />
            </span>
            <h1 className="text-2xl font-black tracking-tight">
              {t("ordering.paymentSuccessTitle")}
            </h1>
            <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
              {t("ordering.paymentSuccessDescription")}
            </p>
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              {orderId ? (
                <Button asChild className="rounded-xl">
                  <Link href={`/orders/${orderId}`}>{t("ordering.backToOrders")}</Link>
                </Button>
              ) : (
                <Button asChild className="rounded-xl">
                  <Link href="/dashboard">{t("ordering.backToOrders")}</Link>
                </Button>
              )}
              <Button asChild variant="outline" className="rounded-xl">
                <Link href="/cart">{t("ordering.backToCart")}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
      <SiteFooter />
    </>
  );
}
