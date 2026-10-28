"use client";

import { create } from "zustand";

import type { ChatProductCard } from "@/infrastructure/http";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
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
  setConversationId: (id: string | null) => void;
  setPending: (pending: boolean) => void;
  setCooldown: (until: number | null) => void;
  reset: () => void;
}

/**
 * Estado do widget de chat em memória (zustand). Nada é persistido:
 * `conversation_id` vive só no processo do navegador e é descartado ao
 * recarregar a página (decisão do projeto). O histórico canônico fica no
 * backend, sempre escopado por dono/tenant.
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
