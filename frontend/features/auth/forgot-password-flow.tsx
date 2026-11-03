"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import type { ZodError } from "zod";

import type {
  PasswordRecoveryRequestInput,
  PasswordRecoveryVerified,
  PasswordRecoveryVerifyInput,
} from "@/core/domain/auth";
import { Link } from "@/i18n/navigation";
import { ApiError, authApi, problemCode } from "@/infrastructure/http";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

import {
  normalizePhoneE164,
  passwordRecoveryRequestSchema,
  passwordRecoveryResetSchema,
  passwordRecoveryVerifySchema,
} from "./schemas";
import { TurnstileWidget } from "./turnstile-widget";

type Step = "request" | "verify" | "reset" | "success";
type Method = "email" | "phone";

interface ForgotPasswordFlowProps {
  siteKey?: string;
  nonce?: string;
}

function zodFieldErrors(error: ZodError): Record<string, string> {
  const result: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = issue.path[0];
    if (typeof key === "string") {
      result[key] ??= issue.message;
    }
  }
  return result;
}

function retryAfter(error: unknown): number | null {
  return error instanceof ApiError ? error.retryAfterSeconds : null;
}

export function ForgotPasswordFlow({ siteKey, nonce }: ForgotPasswordFlowProps) {
  const t = useTranslations("forgotPassword");
  const tRoot = useTranslations();
  const locale = useLocale();
  const headingRef = React.useRef<HTMLHeadingElement>(null);
  const emailRef = React.useRef<HTMLInputElement>(null);
  const phoneRef = React.useRef<HTMLInputElement>(null);
  const codeRef = React.useRef<HTMLInputElement>(null);
  const passwordRef = React.useRef<HTMLInputElement>(null);

  const [step, setStep] = React.useState<Step>("request");
  const [method, setMethod] = React.useState<Method>("email");
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [code, setCode] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [identifierType, setIdentifierType] = React.useState<Method>("email");
  const [identifierValue, setIdentifierValue] = React.useState("");
  const [resetToken, setResetToken] = React.useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = React.useState<string | null>(null);
  const [turnstileKey, setTurnstileKey] = React.useState(0);
  const [turnstileError, setTurnstileError] = React.useState(false);
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const [statusMessage, setStatusMessage] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [resendSeconds, setResendSeconds] = React.useState(0);

  React.useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  React.useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = window.setInterval(() => {
      setResendSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  function resetTurnstile() {
    setTurnstileToken(null);
    setTurnstileError(false);
    setTurnstileKey((current) => current + 1);
  }

  function clearMessages() {
    setFieldErrors({});
    setFormError(null);
    setStatusMessage(null);
  }

  function chooseMethod(next: Method) {
    setMethod(next);
    setEmail("");
    setPhone("");
    clearMessages();
    window.requestAnimationFrame(() => {
      if (next === "email") emailRef.current?.focus();
      else phoneRef.current?.focus();
    });
  }

  function changeEmail(value: string) {
    setEmail(value);
    if (value) setPhone("");
    setMethod("email");
    clearMessages();
  }

  function changePhone(value: string) {
    setPhone(value);
    if (value) setEmail("");
    setMethod("phone");
    clearMessages();
  }

  function changeCode(value: string) {
    setCode(value.replace(/\D/g, "").slice(0, 6));
    clearMessages();
  }

  function changePassword(value: string, confirm = false) {
    if (confirm) setConfirmPassword(value);
    else setNewPassword(value);
    clearMessages();
  }

  function restart() {
    setStep("request");
    setMethod("email");
    setEmail("");
    setPhone("");
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
    setIdentifierType("email");
    setIdentifierValue("");
    setResetToken(null);
    setResendSeconds(0);
    clearMessages();
    resetTurnstile();
  }

  function handleRequestError(error: unknown) {
    const seconds = retryAfter(error);
    const code = problemCode(error);
    if (error instanceof ApiError && error.status === 429) {
      const retry = seconds ?? 60;
      setResendSeconds(retry);
      setFormError(t("rateLimited", { seconds: retry }));
      return;
    }
    if (code === "antibot_verification_failed") {
      setFormError(t("turnstileError"));
      return;
    }
    if (code === "service_unavailable" || (error instanceof ApiError && error.status === 503)) {
      setFormError(t("unavailable"));
      return;
    }
    if (code === "network_error" || (error instanceof ApiError && error.status === 0)) {
      setFormError(t("formError"));
      return;
    }
    setFormError(t("formError"));
  }

  function handleVerifyError(error: unknown) {
    const seconds = retryAfter(error);
    if (error instanceof ApiError && error.status === 429) {
      const retry = seconds ?? 60;
      setFormError(t("rateLimited", { seconds: retry }));
      return;
    }
    if (problemCode(error) === "password_recovery_code_invalid") {
      setFormError(t("invalidCode"));
      return;
    }
    if (error instanceof ApiError && error.status === 503) {
      setFormError(t("unavailable"));
      return;
    }
    setFormError(t("formError"));
  }

  function handleResetError(error: unknown) {
    const seconds = retryAfter(error);
    const code = problemCode(error);
    if (error instanceof ApiError && error.status === 429) {
      const retry = seconds ?? 60;
      setFormError(t("rateLimited", { seconds: retry }));
      return;
    }
    if (code === "password_reuse") {
      setResetToken(null);
      setFormError(t("passwordReuse"));
      return;
    }
    if (code === "password_reset_token_invalid") {
      setResetToken(null);
      setFormError(t("resetTokenInvalid"));
      return;
    }
    if (code === "weak_password") {
      setFormError(t("passwordMin"));
      return;
    }
    if (error instanceof ApiError && error.status === 503) {
      setFormError(t("unavailable"));
      return;
    }
    setFormError(t("formError"));
  }

  async function submitRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();
    const parsed = passwordRecoveryRequestSchema.safeParse({
      email,
      phone,
      turnstile_token: turnstileToken ?? "",
      locale,
    });
    if (!parsed.success) {
      setFieldErrors(zodFieldErrors(parsed.error));
      return;
    }

    setIsSubmitting(true);
    try {
      const input: PasswordRecoveryRequestInput = {
        email: parsed.data.email,
        phone: parsed.data.phone,
        turnstile_token: parsed.data.turnstile_token,
        locale: parsed.data.locale,
      };
      await authApi.requestPasswordRecovery(input);
      setIdentifierType(parsed.data.email ? "email" : "phone");
      setIdentifierValue(parsed.data.email ?? parsed.data.phone ?? "");
      setStatusMessage(t("genericAccepted"));
      setStep("verify");
      setCode("");
      setResendSeconds(60);
      window.requestAnimationFrame(() => codeRef.current?.focus());
    } catch (error) {
      handleRequestError(error);
    } finally {
      setIsSubmitting(false);
      resetTurnstile();
    }
  }

  async function submitVerify(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();
    const parsed = passwordRecoveryVerifySchema.safeParse({
      email: identifierType === "email" ? identifierValue : undefined,
      phone: identifierType === "phone" ? identifierValue : undefined,
      code,
    });
    if (!parsed.success) {
      setFieldErrors(zodFieldErrors(parsed.error));
      return;
    }

    setIsSubmitting(true);
    try {
      const input: PasswordRecoveryVerifyInput = {
        email: parsed.data.email,
        phone: parsed.data.phone,
        code: parsed.data.code,
      };
      const result: PasswordRecoveryVerified = await authApi.verifyPasswordRecovery(input);
      setResetToken(result.reset_token);
      setStep("reset");
      setStatusMessage(null);
      window.requestAnimationFrame(() => passwordRef.current?.focus());
    } catch (error) {
      handleVerifyError(error);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function resendCode() {
    if (resendSeconds > 0 || isSubmitting) return;
    clearMessages();
    if (!turnstileToken) {
      setFormError(t("resendTurnstileHint"));
      return;
    }
    setIsSubmitting(true);
    try {
      await authApi.requestPasswordRecovery({
        email: identifierType === "email" ? identifierValue : undefined,
        phone: identifierType === "phone" ? identifierValue : undefined,
        turnstile_token: turnstileToken,
        locale,
      });
      setStatusMessage(t("genericAccepted"));
      setResendSeconds(60);
    } catch (error) {
      handleRequestError(error);
    } finally {
      setIsSubmitting(false);
      resetTurnstile();
    }
  }

  async function submitReset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();
    if (!resetToken) {
      setFormError(t("resetTokenInvalid"));
      return;
    }
    const parsed = passwordRecoveryResetSchema.safeParse({
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    if (!parsed.success) {
      setFieldErrors(zodFieldErrors(parsed.error));
      return;
    }

    setIsSubmitting(true);
    try {
      await authApi.resetPassword({
        reset_token: resetToken,
        new_password: parsed.data.new_password,
      });
      setStep("success");
      setResetToken(null);
    } catch (error) {
      handleResetError(error);
    } finally {
      setIsSubmitting(false);
    }
  }

  const emailDisabled = isSubmitting || phone.trim().length > 0;
  const phoneDisabled = isSubmitting || email.trim().length > 0;
  const emailValid =
    email.trim().length > 0 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim().toLowerCase());
  const phoneValid = phone.trim().length > 0 && normalizePhoneE164(phone) !== null;
  const identifierValid =
    (email.trim().length > 0 && phone.trim().length === 0 && emailValid) ||
    (phone.trim().length > 0 && email.trim().length === 0 && phoneValid);
  const stepNumber = step === "request" ? 1 : step === "verify" ? 2 : 3;
  const showStepLabel = step !== "success";

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
          {showStepLabel ? t("stepLabel", { current: stepNumber, total: 3 }) : t("successTitle")}
        </p>
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="text-2xl font-semibold tracking-tight outline-none"
        >
          {step === "request"
            ? t("title")
            : step === "verify"
              ? t("codeTitle")
              : step === "reset"
                ? t("resetTitle")
                : t("successTitle")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {step === "request"
            ? t("subtitle")
            : step === "verify"
              ? t("codeSubtitle", { destination: identifierValue })
              : step === "reset"
                ? t("resetSubtitle")
                : t("successSubtitle")}
        </p>
      </div>

      <div aria-live="polite" className="min-h-5 text-sm text-muted-foreground">
        {statusMessage}
      </div>

      {step === "request" ? (
        <form onSubmit={submitRequest} noValidate className="space-y-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="forgot-email">{t("emailLabel")}</Label>
              <Button
                type="button"
                variant="link"
                className="h-auto p-0 text-xs"
                onClick={() => chooseMethod("phone")}
              >
                {t("switchToPhone")}
              </Button>
            </div>
            <Input
              id="forgot-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              value={email}
              disabled={emailDisabled}
              placeholder={t("emailPlaceholder")}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby="forgot-email-help"
              onChange={(event) => changeEmail(event.target.value)}
            />
            <p id="forgot-email-help" className="text-xs text-muted-foreground">
              {t("emailDescription")}
            </p>
            {fieldErrors.email ? (
              <p role="alert" className="text-xs text-destructive">
                {tRoot(fieldErrors.email)}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="forgot-phone">{t("phoneLabel")}</Label>
              <Button
                type="button"
                variant="link"
                className="h-auto p-0 text-xs"
                onClick={() => chooseMethod("email")}
              >
                {t("switchToEmail")}
              </Button>
            </div>
            <Input
              id="forgot-phone"
              ref={phoneRef}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={phone}
              disabled={phoneDisabled}
              placeholder={t("phonePlaceholder")}
              aria-invalid={Boolean(fieldErrors.phone)}
              aria-describedby="forgot-phone-help"
              onChange={(event) => changePhone(event.target.value)}
            />
            <p id="forgot-phone-help" className="text-xs text-muted-foreground">
              {t("phoneDescription")}
            </p>
            <p className="text-xs text-muted-foreground">{t("phoneVerifiedHint")}</p>
            {fieldErrors.phone ? (
              <p role="alert" className="text-xs text-destructive">
                {tRoot(fieldErrors.phone)}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            {siteKey ? (
              <TurnstileWidget
                siteKey={siteKey}
                nonce={nonce}
                language={locale}
                resetKey={turnstileKey}
                onToken={(token) => {
                  setTurnstileToken(token);
                  setTurnstileError(false);
                }}
                onError={() => {
                  setTurnstileToken(null);
                  setTurnstileError(true);
                }}
              />
            ) : (
              <Alert variant="warning">
                <AlertDescription>{t("turnstileUnavailable")}</AlertDescription>
              </Alert>
            )}
            {turnstileError ? (
              <p role="alert" className="text-xs text-destructive">
                {t("turnstileError")}
              </p>
            ) : null}
          </div>

          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <Button
            type="submit"
            className="w-full"
            disabled={
              isSubmitting ||
              resendSeconds > 0 ||
              !siteKey ||
              !turnstileToken ||
              !identifierValid
            }
          >
            {isSubmitting ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <ShieldCheck aria-hidden="true" />
            )}
            {isSubmitting ? t("requestLoading") : t("requestSubmit")}
          </Button>
        </form>
      ) : null}

      {step === "verify" ? (
        <form onSubmit={submitVerify} noValidate className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="forgot-code">{t("codeLabel")}</Label>
            <Input
              id="forgot-code"
              ref={codeRef}
              value={code}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder={t("codePlaceholder")}
              aria-invalid={Boolean(fieldErrors.code)}
              aria-describedby="forgot-code-help"
              onChange={(event) => changeCode(event.target.value)}
            />
            <p id="forgot-code-help" className="text-xs text-muted-foreground">
              {t("codeHint")}
            </p>
            {fieldErrors.code ? (
              <p role="alert" className="text-xs text-destructive">
                {tRoot(fieldErrors.code)}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            {siteKey ? (
              <TurnstileWidget
                siteKey={siteKey}
                nonce={nonce}
                language={locale}
                resetKey={turnstileKey}
                onToken={(token) => {
                  setTurnstileToken(token);
                  setTurnstileError(false);
                }}
                onError={() => {
                  setTurnstileToken(null);
                  setTurnstileError(true);
                }}
              />
            ) : null}
            {turnstileError ? (
              <p role="alert" className="text-xs text-destructive">
                {t("turnstileError")}
              </p>
            ) : null}
          </div>

          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              className="sm:flex-1"
              onClick={() => {
                setStep("request");
                clearMessages();
                resetTurnstile();
              }}
            >
              <ArrowLeft aria-hidden="true" />
              {t("back")}
            </Button>
            <Button type="submit" className="sm:flex-1" disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : null}
              {isSubmitting ? t("verifyLoading") : t("verifySubmit")}
            </Button>
          </div>

          <Button
            type="button"
            variant="ghost"
            className="w-full"
            disabled={resendSeconds > 0 || isSubmitting}
            onClick={() => void resendCode()}
          >
            {resendSeconds > 0 ? t("resendIn", { seconds: resendSeconds }) : t("resend")}
          </Button>
        </form>
      ) : null}

      {step === "reset" ? (
        <form onSubmit={submitReset} noValidate className="space-y-5">
          <Alert variant="warning">
            <AlertDescription>{t("passwordReuseWarning")}</AlertDescription>
          </Alert>

          <div className="space-y-2">
            <Label htmlFor="forgot-new-password">{t("newPasswordLabel")}</Label>
            <Input
              id="forgot-new-password"
              ref={passwordRef}
              type="password"
              autoComplete="new-password"
              value={newPassword}
              aria-invalid={Boolean(fieldErrors.new_password)}
              onChange={(event) => changePassword(event.target.value)}
            />
            {fieldErrors.new_password ? (
              <p role="alert" className="text-xs text-destructive">
                {tRoot(fieldErrors.new_password)}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="forgot-confirm-password">{t("confirmPasswordLabel")}</Label>
            <Input
              id="forgot-confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              aria-invalid={Boolean(fieldErrors.confirm_password)}
              onChange={(event) => changePassword(event.target.value, true)}
            />
            {fieldErrors.confirm_password ? (
              <p role="alert" className="text-xs text-destructive">
                {tRoot(fieldErrors.confirm_password)}
              </p>
            ) : null}
          </div>

          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <Button type="submit" className="w-full" disabled={isSubmitting || !resetToken}>
            {isSubmitting ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : null}
            {isSubmitting ? t("resetLoading") : t("resetSubmit")}
          </Button>

          {!resetToken ? (
            <Button type="button" variant="outline" className="w-full" onClick={restart}>
              {t("restart")}
            </Button>
          ) : null}
        </form>
      ) : null}

      {step === "success" ? (
        <div className="space-y-5">
          <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/5 p-4 text-success">
            <CheckCircle2 aria-hidden="true" className="size-5" />
            <p className="text-sm">{t("successSubtitle")}</p>
          </div>
          <Button asChild className="w-full">
            <Link href="/login">{t("goToLogin")}</Link>
          </Button>
        </div>
      ) : null}

      <p className="text-center text-xs text-muted-foreground">
        <Link href="/login" className="underline underline-offset-4">
          {t("goToLogin")}
        </Link>
      </p>
    </div>
  );
}
