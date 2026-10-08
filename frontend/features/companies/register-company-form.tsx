"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { normalizeCnpj, normalizeCpf } from "@/core/domain";
import type { RegisterCompanyInput } from "@/core/domain/company";
import { companyApi } from "@/infrastructure/http";
import { errorMessageKey } from "@/shared/lib/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

import { registerCompanyFormSchema } from "./schemas";

const INITIAL_VALUES = {
  cnpj: "",
  legal_name: "",
  trade_name: "",
  admin_full_name: "",
  admin_email: "",
  admin_cpf: "",
  password: "",
};

type FormField = keyof typeof INITIAL_VALUES;
type FieldErrors = Partial<Record<FormField, string>>;

function toInput(values: typeof INITIAL_VALUES): RegisterCompanyInput {
  const tradeName = values.trade_name.trim();
  return {
    cnpj: normalizeCnpj(values.cnpj),
    legal_name: values.legal_name.trim(),
    trade_name: tradeName.length > 0 ? tradeName : null,
    admin_full_name: values.admin_full_name.trim(),
    admin_email: values.admin_email.trim(),
    admin_cpf: normalizeCpf(values.admin_cpf),
    password: values.password,
  };
}

export function RegisterCompanyForm() {
  const t = useTranslations();
  const [values, setValues] = React.useState(INITIAL_VALUES);
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  function update(field: FormField) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const parsed = registerCompanyFormSchema.safeParse(values);
    if (!parsed.success) {
      const errors: FieldErrors = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as FormField;
        errors[key] ??= issue.message;
      }
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsLoading(true);
    try {
      await companyApi.register(toInput(values));
      setSubmitted(true);
    } catch (error) {
      setFormError(t(errorMessageKey(error)));
    } finally {
      setIsLoading(false);
    }
  }

  if (submitted) {
    return (
      <Alert variant="success">
        <AlertTitle>{t("onboarding.successTitle")}</AlertTitle>
        <AlertDescription>
          {t("onboarding.successDescription")}{" "}
          <Link href="/login" className="font-medium underline underline-offset-4">
            {t("onboarding.successLogin")}
          </Link>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="cnpj">{t("onboarding.cnpjLabel")}</Label>
          <Input
            id="cnpj"
            inputMode="numeric"
            autoComplete="off"
            value={values.cnpj}
            disabled={isLoading}
            placeholder={t("onboarding.cnpjPlaceholder")}
            aria-invalid={Boolean(fieldErrors.cnpj)}
            onChange={update("cnpj")}
          />
          {fieldErrors.cnpj ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.cnpj)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="trade_name">{t("onboarding.tradeNameLabel")}</Label>
          <Input
            id="trade_name"
            value={values.trade_name}
            disabled={isLoading}
            placeholder={t("onboarding.tradeNamePlaceholder")}
            onChange={update("trade_name")}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="legal_name">{t("onboarding.legalNameLabel")}</Label>
        <Input
          id="legal_name"
          value={values.legal_name}
          disabled={isLoading}
          placeholder={t("onboarding.legalNamePlaceholder")}
          aria-invalid={Boolean(fieldErrors.legal_name)}
          onChange={update("legal_name")}
        />
        {fieldErrors.legal_name ? (
          <p role="alert" className="text-sm text-destructive">
            {t(fieldErrors.legal_name)}
          </p>
        ) : null}
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="admin_full_name">{t("onboarding.adminFullNameLabel")}</Label>
          <Input
            id="admin_full_name"
            autoComplete="name"
            value={values.admin_full_name}
            disabled={isLoading}
            placeholder={t("onboarding.adminFullNamePlaceholder")}
            aria-invalid={Boolean(fieldErrors.admin_full_name)}
            onChange={update("admin_full_name")}
          />
          {fieldErrors.admin_full_name ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.admin_full_name)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="admin_email">{t("onboarding.adminEmailLabel")}</Label>
          <Input
            id="admin_email"
            type="email"
            autoComplete="email"
            value={values.admin_email}
            disabled={isLoading}
            placeholder={t("onboarding.adminEmailPlaceholder")}
            aria-invalid={Boolean(fieldErrors.admin_email)}
            onChange={update("admin_email")}
          />
          {fieldErrors.admin_email ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.admin_email)}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="admin_cpf">{t("onboarding.adminCpfLabel")}</Label>
          <Input
            id="admin_cpf"
            inputMode="numeric"
            autoComplete="off"
            value={values.admin_cpf}
            disabled={isLoading}
            placeholder={t("onboarding.adminCpfPlaceholder")}
            aria-invalid={Boolean(fieldErrors.admin_cpf)}
            onChange={update("admin_cpf")}
          />
          {fieldErrors.admin_cpf ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.admin_cpf)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">{t("onboarding.passwordLabel")}</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={values.password}
            disabled={isLoading}
            aria-invalid={Boolean(fieldErrors.password)}
            onChange={update("password")}
          />
          {fieldErrors.password ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.password)}
            </p>
          ) : null}
        </div>
      </div>

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? t("onboarding.submitLoading") : t("onboarding.submit")}
      </Button>
    </form>
  );
}
