"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { LogoutButton } from "@/features/auth";
import { CompanyProfile } from "@/features/companies";
import { CreditAccountCard } from "@/features/credit";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";

export function DashboardClient() {
  const t = useTranslations();
  const session = useAuthStore((s) => s.session);
  const status = useAuthStore((s) => s.status);

  if (status === "idle") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (status !== "authenticated" || !session) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader>
          <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h1>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>{t("dashboard.loginRequired")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full">
            <Link href="/login">{t("dashboard.loginLink")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("auth.signedInAs")}{" "}
            <span className="font-medium text-foreground">{session.user.email}</span>
          </p>
        </div>
        <LogoutButton />
      </div>

      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline" size="sm">
          <Link href="/catalog">{t("catalog.title")}</Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/cart">{t("cart.title")}</Link>
        </Button>
      </div>

      <CompanyProfile />
      <CreditAccountCard />
    </div>
  );
}
