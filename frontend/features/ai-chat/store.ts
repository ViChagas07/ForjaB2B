"use client";

import { create } from "zustand";

import type { ChatProductCard } from "@/infrastructure/http";
import type { Locale } from "@/i18n/locales";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  /** Idioma persistido no backend para este turno (11 locales). */
  language?: Locale;
  /** Cartões montados pelo BACKEND (imagem/link/preço) — nunca HTML. */
  cards?: ChatProductCard[];
}

interface AiChatState {
  isOpen: boolean;
  /** EM MEMÓRIA: recarregar a página inicia uma nova conversa. */
  conversationId: string | null;
  messages: ChatMessage[];
  pending: boolean;
  /** Fim do bloqueio por 429 (epoch ms) — envio desabilitado até lá. */
  cooldownUntil: number | null;
  open: () => void;
  close: () => void;
  toggle: () => void;
  newConversation: () => void;
  addMessage: (message: ChatMessage) => void;
  setMessageLanguage: (id: string, language: Locale) => void;
  setConversationId: (id: string | null) => void;
  setPending: (pending: boolean) => void;
  setCooldown: (until: number | null) => void;
  reset: () => void;
}

/**
 * Estado do widget de chat em memória (zustand). Nada é persistido:
 * `conversation_id` vive só no processo do navegador e é descartado ao
 * recarregar, trocar de aba/rota ou trocar de idioma (o widget reinicia uma
 * conversa). O histórico canônico fica no backend, sempre escopado por
 * dono/tenant.
 */
export const useAiChatStore = create<AiChatState>((set) => ({
  isOpen: false,
  conversationId: null,
  messages: [],
  pending: false,
  cooldownUntil: null,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  newConversation: () =>
    set({ conversationId: null, messages: [], pending: false, cooldownUntil: null }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessageLanguage: (id, language) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === id ? { ...message, language } : message,
      ),
    })),
  setConversationId: (conversationId) => set({ conversationId }),
  setPending: (pending) => set({ pending }),
  setCooldown: (cooldownUntil) => set({ cooldownUntil }),
  reset: () =>
    set({
      isOpen: false,
      conversationId: null,
      messages: [],
      pending: false,
      cooldownUntil: null,
    }),
}));
