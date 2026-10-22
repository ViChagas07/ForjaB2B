import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SiteHeader } from "@/shared/components/site-header";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.paymentCancelTitle") };
}

export default async function CheckoutCancelPage() {
  const t = await getTranslations();

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <Card className="mx-auto w-full max-w-lg">
          <CardHeader>
            <CardTitle>{t("ordering.paymentCancelTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t("ordering.paymentCancelDescription")}
            </p>
            <Button asChild>
              <Link href="/cart">{t("ordering.backToCart")}</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
