"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import type { AccountType } from "@/core/domain/auth";
import { RegisterCompanyForm } from "@/features/companies";
import { RegisterConsumerForm } from "@/features/consumers";

import { AccountTypeToggle } from "./account-type-toggle";

interface RegisterTabsProps {
  initialType?: AccountType;
  initialEmail?: string;
  initialFullName?: string;
}

export function RegisterTabs({
  initialType = "COMPANY",
  initialEmail,
  initialFullName,
}: RegisterTabsProps) {
  const t = useTranslations();
  const [accountType, setAccountType] = React.useState<AccountType>(initialType);

  const isPerson = accountType === "PERSON";

  return (
    <div className="space-y-6">
      <AccountTypeToggle value={accountType} onChange={setAccountType} />

      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">
          {isPerson ? t("consumer.title") : t("onboarding.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isPerson ? t("consumer.subtitle") : t("onboarding.subtitle")}
        </p>
      </div>

      {isPerson ? (
        <RegisterConsumerForm
          key={`person:${initialEmail ?? ""}:${initialFullName ?? ""}`}
          initialEmail={initialEmail}
          initialFullName={initialFullName}
        />
      ) : (
        <RegisterCompanyForm />
      )}
    </div>
  );
}
