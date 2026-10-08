"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { errorMessageKey } from "@/shared/lib/api-error";
import { login } from "@/shared/stores/auth-actions";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

import { loginFormSchema } from "./schemas";
import { GoogleLoginButton } from "./google-login-button";

type FieldErrors = Partial<Record<"email" | "password", string>>;

export function LoginForm() {
  const t = useTranslations();
  const router = useRouter();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const parsed = loginFormSchema.safeParse({ email, password });
    if (!parsed.success) {
      const errors: FieldErrors = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as "email" | "password";
        errors[key] ??= issue.message;
      }
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsLoading(true);
    try {
      await login(parsed.data.email, parsed.data.password);
      router.replace("/dashboard");
      router.refresh();
    } catch (error) {
      setFormError(t(errorMessageKey(error)));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="login-email">{t("auth.emailLabel")}</Label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          disabled={isLoading}
          placeholder={t("auth.emailPlaceholder")}
          aria-invalid={Boolean(fieldErrors.email)}
          onChange={(event) => setEmail(event.target.value)}
        />
        {fieldErrors.email ? (
          <p role="alert" className="text-sm text-destructive">
            {t(fieldErrors.email)}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="login-password">{t("auth.passwordLabel")}</Label>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          disabled={isLoading}
          placeholder={t("auth.passwordPlaceholder")}
          aria-invalid={Boolean(fieldErrors.password)}
          onChange={(event) => setPassword(event.target.value)}
        />
        {fieldErrors.password ? (
          <p role="alert" className="text-sm text-destructive">
            {t(fieldErrors.password)}
          </p>
        ) : null}
      </div>

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? t("auth.loginLoading") : t("auth.loginSubmit")}
      </Button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">{t("auth.loginOr")}</span>
        </div>
      </div>

      <GoogleLoginButton />
    </form>
  );
}
