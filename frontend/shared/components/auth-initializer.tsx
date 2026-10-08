"use client";

import * as React from "react";

import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Hidrata o estado de autenticação a partir do localStorage uma única vez no
 * cliente (após o primeiro render). Sem isso, a store começaria "idle" para
 * sempre e as páginas protegidas nunca saberiam que há sessão.
 */
export function AuthInitializer() {
  React.useEffect(() => {
    useAuthStore.getState().hydrate();
  }, []);

  return null;
}
