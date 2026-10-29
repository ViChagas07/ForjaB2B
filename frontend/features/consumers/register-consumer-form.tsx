"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { normalizeCpf } from "@/core/domain";
import type { Gender, RegisterConsumerInput } from "@/core/domain/consumer";
import { useConsumerApi } from "@/infrastructure/http";
import { errorMessageKey } from "@/shared/lib/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Checkbox } from "@/shared/ui/checkbox";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";

import { normalizePostalCode, registerConsumerFormSchema } from "./schemas";

interface RegisterConsumerFormProps {
  initialEmail?: string;
  initialFullName?: string;
}

const INITIAL_GENDER: Gender = "PREFIRO_NAO_INFORMAR";

function initialValues({ initialEmail, initialFullName }: RegisterConsumerFormProps) {
  return {
    full_name: initialFullName ?? "",
    email: initialEmail ?? "",
    password: "",
    birth_date: "",
    cpf: "",
    postal_code: "",
    gender: INITIAL_GENDER as Gender,
    consent: false,
  };
}

type FormField = keyof ReturnType<typeof initialValues>;
type FieldErrors = Partial<Record<FormField, string>>;

function toInput(values: ReturnType<typeof initialValues>): RegisterConsumerInput {
  return {
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    password: values.password,
    cpf: normalizeCpf(values.cpf),
    birth_date: values.birth_date,
    postal_code: normalizePostalCode(values.postal_code),
    gender: values.gender,
    consent: values.consent,
  };
}

export function RegisterConsumerForm(props: RegisterConsumerFormProps) {
  const t = useTranslations();
  const { register } = useConsumerApi();
  const [values, setValues] = React.useState(() => initialValues(props));
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  function update(field: FormField) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  function updateConsent(event: React.ChangeEvent<HTMLInputElement>) {
    setValues((current) => ({ ...current, consent: event.target.checked }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const parsed = registerConsumerFormSchema.safeParse(values);
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
      await register(toInput(values));
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
        <AlertTitle>{t("consumer.successTitle")}</AlertTitle>
        <AlertDescription>
          {t("consumer.successDescription")}{" "}
          <Link href="/login?tipo=cpf" className="font-medium underline underline-offset-4">
            {t("consumer.successLogin")}
          </Link>
        </AlertDescription>
      </Alert>
    );
  }

  const genderOptions: Gender[] = [
    "FEMININO",
    "MASCULINO",
    "NAO_BINARIO",
    "OUTRO",
    "PREFIRO_NAO_INFORMAR",
  ];

  function genderLabelKey(gender: Gender): string {
    switch (gender) {
      case "FEMININO":
        return "consumer.genderFemale";
      case "MASCULINO":
        return "consumer.genderMale";
      case "NAO_BINARIO":
        return "consumer.genderNonBinary";
      case "OUTRO":
        return "consumer.genderOther";
      default:
        return "consumer.genderPreferNotToSay";
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="consumer_full_name">{t("consumer.fullNameLabel")}</Label>
        <Input
          id="consumer_full_name"
          autoComplete="name"
          value={values.full_name}
          disabled={isLoading}
          placeholder={t("consumer.fullNamePlaceholder")}
          aria-invalid={Boolean(fieldErrors.full_name)}
          onChange={update("full_name")}
        />
        {fieldErrors.full_name ? (
          <p role="alert" className="text-sm text-destructive">
            {t(fieldErrors.full_name)}
          </p>
        ) : null}
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="consumer_email">{t("auth.emailLabel")}</Label>
          <Input
            id="consumer_email"
            type="email"
            autoComplete="email"
            value={values.email}
            disabled={isLoading}
            placeholder={t("auth.emailPlaceholder")}
            aria-invalid={Boolean(fieldErrors.email)}
            onChange={update("email")}
          />
          {fieldErrors.email ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.email)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="consumer_password">{t("auth.passwordLabel")}</Label>
          <Input
            id="consumer_password"
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

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="consumer_birth_date">{t("consumer.birthDateLabel")}</Label>
          <Input
            id="consumer_birth_date"
            type="date"
            autoComplete="bday"
            value={values.birth_date}
            disabled={isLoading}
            aria-invalid={Boolean(fieldErrors.birth_date)}
            onChange={update("birth_date")}
          />
          {fieldErrors.birth_date ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.birth_date)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="consumer_cpf">{t("consumer.cpfLabel")}</Label>
          <Input
            id="consumer_cpf"
            inputMode="numeric"
            autoComplete="off"
            value={values.cpf}
            disabled={isLoading}
            placeholder={t("consumer.cpfPlaceholder")}
            aria-invalid={Boolean(fieldErrors.cpf)}
            onChange={update("cpf")}
          />
          {fieldErrors.cpf ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.cpf)}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="consumer_postal_code">{t("consumer.postalCodeLabel")}</Label>
          <Input
            id="consumer_postal_code"
            inputMode="numeric"
            autoComplete="postal-code"
            value={values.postal_code}
            disabled={isLoading}
            placeholder={t("consumer.postalCodePlaceholder")}
            aria-invalid={Boolean(fieldErrors.postal_code)}
            onChange={update("postal_code")}
          />
          {fieldErrors.postal_code ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.postal_code)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="consumer_gender">{t("consumer.genderLabel")}</Label>
          <Select
            value={values.gender}
            disabled={isLoading}
            onValueChange={(value) =>
              setValues((current) => ({ ...current, gender: value as Gender }))
            }
          >
            <SelectTrigger id="consumer_gender" aria-invalid={Boolean(fieldErrors.gender)}>
              <SelectValue placeholder={t("consumer.genderPlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {genderOptions.map((gender) => (
                <SelectItem key={gender} value={gender}>
                  {t(genderLabelKey(gender))}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {fieldErrors.gender ? (
            <p role="alert" className="text-sm text-destructive">
              {t(fieldErrors.gender)}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-start gap-3">
          <Checkbox
            id="consumer_consent"
            name="consent"
            checked={values.consent}
            required
            disabled={isLoading}
            aria-invalid={Boolean(fieldErrors.consent)}
            onChange={updateConsent}
          />
          <Label
            htmlFor="consumer_consent"
            className="text-sm font-normal leading-relaxed text-muted-foreground"
          >
            {t.rich("onboarding.consentLabel", {
              terms: (chunks) => (
                <Link
                  href="/privacy"
                  className="font-medium text-foreground underline underline-offset-4"
                >
                  {chunks}
                </Link>
              ),
              privacy: (chunks) => (
                <Link
                  href="/privacy"
                  className="font-medium text-foreground underline underline-offset-4"
                >
                  {chunks}
                </Link>
              ),
            })}
          </Label>
        </div>
        {fieldErrors.consent ? (
          <p role="alert" className="text-sm text-destructive">
            {t(fieldErrors.consent)}
          </p>
        ) : null}
      </div>

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" className="w-full" disabled={isLoading || !values.consent}>
        {isLoading ? t("consumer.submitLoading") : t("consumer.submit")}
      </Button>
    </form>
  );
}
