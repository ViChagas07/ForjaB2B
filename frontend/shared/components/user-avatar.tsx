"use client";

import * as React from "react";

import type { UserProfile } from "@/core/domain/auth";
import { cn } from "@/shared/lib/utils";

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  const first = parts[0];
  const last = parts[parts.length - 1];
  if (!first || !last) {
    return "?";
  }
  if (parts.length === 1) {
    return first.slice(0, 2).toUpperCase();
  }
  return `${first[0]}${last[0]}`.toUpperCase();
}

interface UserAvatarProps {
  user: UserProfile;
  className?: string;
}

/**
 * Moldura de perfil do header.
 *
 * Usa a foto do Google (quando o login foi OIDC) e cai para as iniciais do
 * nome em contas CPF/CNPJ ou se a imagem externa falhar. A CSP libera apenas
 * o host de avatar do Google; qualquer outra URL falha e mostra as iniciais.
 */
export function UserAvatar({ user, className }: UserAvatarProps) {
  const [imageFailed, setImageFailed] = React.useState(false);
  const avatarUrl = imageFailed ? null : user.avatar_url;

  React.useEffect(() => {
    setImageFailed(false);
  }, [user.avatar_url]);

  return (
    <span
      className={cn(
        "relative inline-flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-primary/70 bg-primary/15 text-[10px] font-bold uppercase tracking-wide text-white",
        className,
      )}
      aria-hidden="true"
    >
      <span>{initials(user.full_name)}</span>
      {avatarUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={avatarUrl}
          alt=""
          referrerPolicy="no-referrer"
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setImageFailed(true)}
        />
      ) : null}
    </span>
  );
}
