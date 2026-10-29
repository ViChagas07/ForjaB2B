"use client";

import { ArrowRight, ShoppingCart, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { LogoutButton } from "@/features/auth";
import { CompanyProfile } from "@/features/companies";
import { CreditAccountCard } from "@/features/credit";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";

export function DashboardClient() {
  const t = useTranslations();
  const session = useAuthStore((s) => s.session);
  const status = useAuthStore((s) => s.status);

  if (status === "idle") {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <Skeleton className="h-56 w-full rounded-3xl" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (status !== "authenticated" || !session) {
    return (
      <Card className="mx-auto w-full max-w-md rounded-2xl">
        <CardHeader>
          <h1 className="text-2xl font-black tracking-tight">{t("dashboard.title")}</h1>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>{t("dashboard.loginRequired")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full rounded-xl">
            <Link href="/login">{t("dashboard.loginLink")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const isConsumer = (session.user.account_type ?? "COMPANY") === "PERSON";

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section className="surface-ink amber-glow relative overflow-hidden rounded-3xl p-7 sm:p-10">
        <div aria-hidden="true" className="soft-grid absolute inset-0 opacity-40" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
              <Sparkles aria-hidden="true" className="h-3 w-3" />
              {t("dashboard.title")}
            </span>
            <h1 className="mt-4 text-3xl font-black leading-tight tracking-tight text-white sm:text-4xl">
              {session.user.full_name}
            </h1>
            <p className="mt-2 text-sm text-white/65">
              {t("auth.signedInAs")} {session.user.email}
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              <Button asChild className="h-11 rounded-xl px-5">
                <Link href="/catalog">
                  {t("catalog.title")}
                  <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="h-11 rounded-xl border-white/15 bg-white/[0.04] px-5 text-white hover:bg-white/10 hover:text-white"
              >
                <Link href="/cart">
                  <ShoppingCart aria-hidden="true" />
                  {t("cart.title")}
                </Link>
              </Button>
            </div>
          </div>

          <div className="flex flex-col items-start gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-5 lg:min-w-52">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/60">
              {isConsumer ? t("dashboard.accountType") : t("company.status")}
            </p>
            <Badge className="border-transparent bg-primary text-primary-foreground">
              {isConsumer ? t("dashboard.consumerBadge") : session.user.role}
            </Badge>
            <LogoutButton />
          </div>
        </div>
      </section>

      {!isConsumer ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <CompanyProfile />
          <CreditAccountCard />
        </div>
      ) : null}
    </div>
  );
}
