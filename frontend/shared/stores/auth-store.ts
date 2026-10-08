import { create } from "zustand";

import type { AuthSession } from "@/core/domain/auth";

import { clearStoredSession, loadStoredSession, saveStoredSession } from "./auth-storage";

/**
 * Estado de autenticação (cliente) centralizado via Zustand — a fonte de
 * verdade da sessão na UI. Segue o mesmo padrão do `ui-store`: estado de
 * cliente puro, sem cache de dados do servidor.
 *
 * - `idle`: ainda não hidratado (primeiro render / SSR).
 * - `authenticated`: sessão presente.
 * - `unauthenticated`: sem sessão.
 *
 * A orquestração de rede (login/refresh/logout) vive em `auth-actions.ts` e
 * chama os setters daqui; a store em si não faz chamadas HTTP.
 */

export type AuthStatus = "idle" | "authenticated" | "unauthenticated";

interface AuthState {
  session: AuthSession | null;
  status: AuthStatus;
  hydrate: () => void;
  setSession: (session: AuthSession) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  session: null,
  status: "idle",

  hydrate: () => {
    const stored = loadStoredSession();
    set({ session: stored, status: stored ? "authenticated" : "unauthenticated" });
  },

  setSession: (session) => {
    saveStoredSession(session);
    set({ session, status: "authenticated" });
  },

  clearSession: () => {
    clearStoredSession();
    set({ session: null, status: "unauthenticated" });
  },
}));
