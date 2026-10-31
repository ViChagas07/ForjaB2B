"use client";

import * as React from "react";
import { Camera, Loader2, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";

import type { AccountProfile } from "@/core/domain/account";
import { AVATAR_ACCEPT, AVATAR_MAX_BYTES, isAcceptedAvatarType } from "@/core/domain/avatar";
import { useRemoveAvatar, useUploadAvatar } from "@/features/account/hooks";
import { UserAvatar } from "@/shared/components/user-avatar";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

interface AvatarMessage {
  tone: "success" | "error";
  key: string;
}

/**
 * Foto de perfil com envio/remocao sem reload.
 *
 * O arquivo e validado no cliente (tipo e 2 MB) e novamente no backend, que
 * identifica o formato pelos magic bytes. Depois do upload, o hook atualiza a
 * query da conta e a sessao do header, entao o novo avatar aparece na hora.
 */
export function AccountAvatarCard({
  profile,
  fallbackAvatarUrl = null,
}: {
  profile: AccountProfile;
  fallbackAvatarUrl?: string | null;
}) {
  const t = useTranslations("account");
  const upload = useUploadAvatar();
  const remove = useRemoveAvatar();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [message, setMessage] = React.useState<AvatarMessage | null>(null);

  const avatarUrl = profile.avatar_url ?? fallbackAvatarUrl;
  const isPending = upload.isPending || remove.isPending;

  function handleFile(event: React.ChangeEvent<HTMLInputElement>): void {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setMessage(null);

    if (!isAcceptedAvatarType(file.type)) {
      setMessage({ tone: "error", key: "avatarTypeError" });
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      setMessage({ tone: "error", key: "avatarSizeError" });
      return;
    }

    upload.mutate(file, {
      onSuccess: () => setMessage({ tone: "success", key: "avatarSaved" }),
      onError: () => setMessage({ tone: "error", key: "avatarError" }),
    });
  }

  function handleRemove(): void {
    setMessage(null);
    remove.mutate(undefined, {
      onSuccess: () => setMessage({ tone: "success", key: "avatarRemoved" }),
      onError: () => setMessage({ tone: "error", key: "avatarError" }),
    });
  }

  return (
    <Card className="rounded-2xl">
      <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <UserAvatar
          user={{ full_name: profile.full_name, avatar_url: avatarUrl }}
          className="h-20 w-20 text-lg"
        />

        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-bold">{profile.full_name}</p>
          <p className="truncate text-sm text-muted-foreground">{profile.email}</p>
          <p id="avatar-hint" className="mt-1 text-xs text-muted-foreground">
            {t("avatarHint")}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isPending}
              aria-describedby="avatar-hint"
              onClick={() => inputRef.current?.click()}
            >
              {upload.isPending ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <Camera aria-hidden="true" className="h-4 w-4" />
              )}
              {upload.isPending ? t("avatarUploading") : t("avatarChange")}
            </Button>
            {avatarUrl ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={isPending}
                aria-describedby="avatar-hint"
                onClick={handleRemove}
              >
                {remove.isPending ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 aria-hidden="true" className="h-4 w-4" />
                )}
                {remove.isPending ? t("avatarRemoving") : t("avatarRemove")}
              </Button>
            ) : null}
            <input
              ref={inputRef}
              type="file"
              accept={AVATAR_ACCEPT}
              className="sr-only"
              aria-label={t("avatarChange")}
              onChange={handleFile}
            />
          </div>

          {message ? (
            <p
              role={message.tone === "error" ? "alert" : "status"}
              className={
                message.tone === "error"
                  ? "mt-2 text-xs font-medium text-destructive"
                  : "mt-2 text-xs font-medium text-success"
              }
            >
              {t(message.key)}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
