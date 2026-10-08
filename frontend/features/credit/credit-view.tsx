"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatDate, formatMoney, DEFAULT_CURRENCY } from "@/shared/lib/money";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { errorMessageKey } from "@/shared/lib/api-error";

import { useCreditAccount, useCreditEntries } from "./hooks";

/** Cartão de conta de crédito (limite / utilizado / disponível). */
export function CreditAccountCard() {
  const t = useTranslations();
  const locale = useLocale();
  const query = useCreditAccount();

  if (query.isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 p-6">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("credit.accountLoadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(query.error))}</AlertDescription>
      </Alert>
    );
  }

  const account = query.data;
  if (!account) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("credit.noAccount")}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("credit.accountTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-sm text-muted-foreground">{t("credit.available")}</p>
          <p className="text-xl font-semibold">
            {formatMoney(account.available, DEFAULT_CURRENCY, locale)}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{t("credit.limit")}</p>
          <p className="text-xl font-semibold">
            {formatMoney(account.credit_limit, DEFAULT_CURRENCY, locale)}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{t("credit.used")}</p>
          <p className="text-xl font-semibold">
            {formatMoney(account.used, DEFAULT_CURRENCY, locale)}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

/** Histórico de crédito (ledger), somente leitura. */
export function CreditEntriesList() {
  const t = useTranslations();
  const locale = useLocale();
  const query = useCreditEntries();

  if (query.isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("credit.entriesLoadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(query.error))}</AlertDescription>
      </Alert>
    );
  }

  const entries = query.data ?? [];
  if (entries.length === 0) {
    return (
      <Alert variant="info">
        <AlertDescription>{t("credit.entriesEmpty")}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("credit.entriesTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="divide-y">
        {entries.map((entry) => (
          <div key={entry.id} className="flex items-center justify-between py-3 text-sm">
            <div>
              <p className="font-medium">{entry.entry_type}</p>
              {entry.description ? (
                <p className="text-muted-foreground">{entry.description}</p>
              ) : null}
            </div>
            <div className="text-right">
              <p className="font-semibold">{formatMoney(entry.amount, DEFAULT_CURRENCY, locale)}</p>
              <p className="text-xs text-muted-foreground">
                {formatDate(entry.created_at, locale)}
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
