"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Save } from "lucide-react";

import { GENDERS, type Gender } from "@/core/domain/account";
import { useAccount, useUpdateAccount } from "@/features/account/hooks";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/infrastructure/http";
import { UserAvatar } from "@/shared/components/user-avatar";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";

interface AccountForm {
  full_name: string;
  phone: string;
  birth_date: string;
  gender: Gender | "";
  postal_code: string;
}

const EMPTY_FORM: AccountForm = {
  full_name: "",
  phone: "",
  birth_date: "",
  gender: "",
  postal_code: "",
};

function normalizePostalCode(value: string): string {
  return value.replace(/\D/g, "").slice(0, 8);
}

export function AccountClient() {
  const t = useTranslations("account");
  const session = useAuthStore((state) => state.session);
  const authStatus = useAuthStore((state) => state.status);
  const accountQuery = useAccount();
  const updateMutation = useUpdateAccount();
  const [form, setForm] = useState<AccountForm>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [successKey, setSuccessKey] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    const profile = accountQuery.data;
    if (!profile) return;
    setForm({
      full_name: profile.full_name,
      phone: profile.phone ?? "",
      birth_date: profile.birth_date ?? "",
      gender: profile.gender ?? "",
      postal_code: profile.postal_code ?? "",
    });
  }, [accountQuery.data]);

  if (authStatus === "idle" || accountQuery.isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  if (authStatus !== "authenticated") {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>{t("loginRequiredTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("loginRequired")}</p>
          <Button asChild className="w-full">
            <Link href="/login">{t("goToLogin")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (accountQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("loadError")}</AlertTitle>
        <AlertDescription>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void accountQuery.refetch()}
          >
            {t("retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const profile = accountQuery.data;
  if (!profile) return null;

  function change(patch: Partial<AccountForm>) {
    setForm((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      for (const key of Object.keys(patch)) delete next[key];
      return next;
    });
    setSuccessKey(null);
    setSubmitError(null);
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (form.full_name.trim().length < 2) {
      next.full_name = "errors.name";
    }
    if (form.postal_code && normalizePostalCode(form.postal_code).length !== 8) {
      next.postal_code = "errors.postalCode";
    }
    if (form.birth_date) {
      const birth = new Date(`${form.birth_date}T00:00:00`);
      if (Number.isNaN(birth.getTime()) || birth > new Date()) {
        next.birth_date = "errors.birthDate";
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit() {
    if (!validate()) return;
    setSubmitError(null);
    setSuccessKey(null);
    updateMutation.mutate(
      {
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        birth_date: form.birth_date || null,
        gender: form.gender || null,
        postal_code: normalizePostalCode(form.postal_code) || null,
      },
      {
        onSuccess: () => setSuccessKey("saved"),
        onError: (error) =>
          setSubmitError(
            error instanceof ApiError && error.status === 422 ? "errors.invalid" : "errors.generic",
          ),
      },
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Card className="rounded-2xl">
        <CardContent className="flex items-center gap-4 p-5">
          {session ? <UserAvatar user={session.user} className="h-16 w-16" /> : null}
          <div className="min-w-0">
            <p className="truncate text-lg font-bold">{profile.full_name}</p>
            <p className="truncate text-sm text-muted-foreground">{profile.email}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("avatarHint")}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            {successKey ? (
              <Alert variant="success">
                <AlertDescription>{t(successKey)}</AlertDescription>
              </Alert>
            ) : null}
            {submitError ? (
              <Alert variant="destructive">
                <AlertDescription>{t(submitError)}</AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="account-name">{t("name")}</Label>
                <Input
                  id="account-name"
                  value={form.full_name}
                  autoComplete="name"
                  aria-invalid={Boolean(errors.full_name)}
                  onChange={(event) => change({ full_name: event.target.value })}
                />
                {errors.full_name ? (
                  <p className="text-xs text-destructive" role="alert">
                    {t(errors.full_name)}
                  </p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-email">{t("email")}</Label>
                <Input id="account-email" value={profile.email} disabled />
                <p className="text-xs text-muted-foreground">{t("emailHint")}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-phone">{t("phone")}</Label>
                <Input
                  id="account-phone"
                  value={form.phone}
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+55 11 99999-9999"
                  onChange={(event) => change({ phone: event.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-birth">{t("birthDate")}</Label>
                <Input
                  id="account-birth"
                  type="date"
                  value={form.birth_date}
                  aria-invalid={Boolean(errors.birth_date)}
                  onChange={(event) => change({ birth_date: event.target.value })}
                />
                {errors.birth_date ? (
                  <p className="text-xs text-destructive" role="alert">
                    {t(errors.birth_date)}
                  </p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-gender">{t("gender")}</Label>
                <Select
                  value={form.gender || "NONE"}
                  onValueChange={(value) =>
                    change({ gender: value === "NONE" ? "" : (value as Gender) })
                  }
                >
                  <SelectTrigger id="account-gender">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NONE">{t("genderNone")}</SelectItem>
                    {GENDERS.map((gender) => (
                      <SelectItem key={gender} value={gender}>
                        {t(`genders.${gender}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="account-postal-code">{t("postalCode")}</Label>
                <Input
                  id="account-postal-code"
                  value={form.postal_code}
                  inputMode="numeric"
                  autoComplete="postal-code"
                  placeholder="00000-000"
                  aria-invalid={Boolean(errors.postal_code)}
                  onChange={(event) =>
                    change({ postal_code: normalizePostalCode(event.target.value) })
                  }
                />
                {errors.postal_code ? (
                  <p className="text-xs text-destructive" role="alert">
                    {t(errors.postal_code)}
                  </p>
                ) : null}
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Save aria-hidden="true" className="h-4 w-4" />
                )}
                {updateMutation.isPending ? t("saving") : t("save")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
