"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { companyApi, problemCode } from "@/infrastructure/http";
import { errorMessageKey } from "@/shared/lib/api-error";
import { refreshSession } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";

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
  const session = useAuthStore((s) => s.session);
  const status = useAuthStore((s) => s.status);

  const query = useQuery({
    queryKey: ["company", "me"],
    enabled: status === "authenticated" && Boolean(session),
    queryFn: async () => {
      const token = useAuthStore.getState().session?.access_token;
      if (!token) {
        throw new Error("unauthenticated");
      }
      try {
        return await companyApi.getMe(token);
      } catch (error) {
        // Access token expirado/inválido: rotaciona via refresh (atualiza a
        // store) e repete a consulta com o token novo. Se o refresh falhar,
        // a sessão é limpa e o guard da página redireciona ao login.
        const code = problemCode(error);
        if (code === "token_expired" || code === "invalid_token") {
          await refreshSession();
          const newToken = useAuthStore.getState().session?.access_token;
          if (newToken) {
            return companyApi.getMe(newToken);
          }
        }
        throw error;
      }
    },
  });

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("company.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.legalName")}</dt>
            <dd className="font-medium">{company.legal_name}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.tradeName")}</dt>
            <dd className="font-medium">{company.trade_name ?? t("company.notProvided")}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.cnpj")}</dt>
            <dd className="font-mono font-medium">{company.cnpj}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">{t("company.status")}</dt>
            <dd className="font-medium">{statusKey ? t(statusKey) : company.status}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
