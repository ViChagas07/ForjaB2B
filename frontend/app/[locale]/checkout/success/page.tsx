import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SiteHeader } from "@/shared/components/site-header";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

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
      <main id="main" className="container flex-1 py-10">
        <Card className="mx-auto w-full max-w-lg">
          <CardHeader>
            <CardTitle>{t("ordering.paymentSuccessTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t("ordering.paymentSuccessDescription")}
            </p>
            <div className="flex flex-wrap gap-3">
              {orderId ? (
                <Button asChild>
                  <Link href={`/orders/${orderId}`}>{t("ordering.backToOrders")}</Link>
                </Button>
              ) : (
                <Button asChild>
                  <Link href="/orders">{t("ordering.backToOrders")}</Link>
                </Button>
              )}
              <Button asChild variant="outline">
                <Link href="/cart">{t("ordering.backToCart")}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
