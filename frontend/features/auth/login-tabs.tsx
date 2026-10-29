"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import type { AccountType } from "@/core/domain/auth";
import { Link } from "@/i18n/navigation";

import { AccountTypeToggle } from "./account-type-toggle";
import { LoginForm } from "./login-form";

interface LoginTabsProps {
  initialType?: AccountType;
}

export function LoginTabs({ initialType = "PERSON" }: LoginTabsProps) {
  const t = useTranslations();
  const [accountType, setAccountType] = React.useState<AccountType>(initialType);

  const isPerson = accountType === "PERSON";
  const registerHref = isPerson ? "/onboarding?tipo=cpf" : "/onboarding?tipo=cnpj";

  return (
    <div className="space-y-6">
      <AccountTypeToggle value={accountType} onChange={setAccountType} />

      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.loginTitle")}</h1>
        <p className="text-sm text-muted-foreground">
          {isPerson ? t("auth.loginSubtitlePerson") : t("auth.loginSubtitleCompany")}
        </p>
        {!isPerson ? (
          <p className="text-sm text-muted-foreground">{t("auth.companyPasswordOnly")}</p>
        ) : null}
      </div>

      <LoginForm key={accountType} accountType={accountType} />

      <p className="text-center text-sm text-muted-foreground">
        {t("auth.loginNoAccount")}{" "}
        <Link
          href={registerHref}
          className="font-medium text-foreground underline underline-offset-4"
        >
          {t("auth.loginCreateAccount")}
        </Link>
      </p>
    </div>
  );
}
