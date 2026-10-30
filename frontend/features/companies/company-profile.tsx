"use client";

import { useTranslations } from "next-intl";

import { errorMessageKey } from "@/shared/lib/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";

import { useCurrentCompany } from "./use-current-company";

function statusLabelKey(status: string): string {
  switch (status) {
    case "PENDING":
      return "company.statusPending";
    case "ACTIVE":
      return "company.statusActive";
    case "SUSPENDED":
      return "company.statusSuspended";
    case "REJECTED":
      return "company.statusRejected";
    default:
      return "";
  }
}

export function CompanyProfile() {
  const t = useTranslations();
  const query = useCurrentCompany();

  if (query.isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 p-6">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-56" />
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("company.loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(query.error))}</AlertDescription>
      </Alert>
    );
  }

  const company = query.data;
  if (!company) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("company.notFound")}</AlertDescription>
      </Alert>
    );
  }

  const statusKey = statusLabelKey(company.status);
  const isPerson = company.account_type === "PERSON";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{isPerson ? t("company.personalTitle") : t("company.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.legalName")}</dt>
            <dd className="font-medium">{company.legal_name}</dd>
          </div>
          {!isPerson ? (
            <div>
              <dt className="text-sm text-muted-foreground">{t("company.tradeName")}</dt>
              <dd className="font-medium">{company.trade_name ?? t("company.notProvided")}</dd>
            </div>
          ) : null}
          {company.cnpj ? (
            <div>
              <dt className="text-sm text-muted-foreground">{t("company.cnpj")}</dt>
              <dd className="font-mono font-medium">{company.cnpj}</dd>
            </div>
          ) : null}
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.status")}</dt>
            <dd className="font-medium">{statusKey ? t(statusKey) : company.status}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
