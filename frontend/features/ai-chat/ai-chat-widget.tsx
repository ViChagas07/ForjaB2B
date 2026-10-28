"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { Bot, MessageSquarePlus, Send, Sparkles, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { useAuthStore } from "@/shared/stores/auth-store";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Link } from "@/i18n/navigation";
import { ApiError, sendChatMessage } from "@/infrastructure/http";

import { ChatProductCardView } from "./product-card";
import { type ChatMessage, useAiChatStore } from "./store";

const MAX_CHARS = 500;
const RATE_LIMIT_COOLDOWN_MS = 30_000;
const SUGGESTION_KEYS = ["suggestion1", "suggestion2", "suggestion3"] as const;

type ChatError = "rateLimited" | "unavailable" | "timeout" | "generic";

/**
 * Widget do assistente de IA: gatilho no navbar (ícone com animação de hover)
 * e painel de conversa. Conversa vive EM MEMÓRIA (store zustand) — recarregar
 * inicia outra. Mensagens do assistente são TEXTO PURO; links/imagens só nos
 * cartões montados pelo backend. Erros nunca expõem detalhe técnico.
 */
export function AiChatWidget() {
  const t = useTranslations("aiChat");
  const locale = useLocale();
  const status = useAuthStore((s) => s.status);
  const session = useAuthStore((s) => s.session);

  const isOpen = useAiChatStore((s) => s.isOpen);
  const messages = useAiChatStore((s) => s.messages);
  const pending = useAiChatStore((s) => s.pending);
  const cooldownUntil = useAiChatStore((s) => s.cooldownUntil);
  const conversationId = useAiChatStore((s) => s.conversationId);
  const open = useAiChatStore((s) => s.open);
  const close = useAiChatStore((s) => s.close);
  const newConversation = useAiChatStore((s) => s.newConversation);
  const addMessage = useAiChatStore((s) => s.addMessage);
  const setConversationId = useAiChatStore((s) => s.setConversationId);
  const setPending = useAiChatStore((s) => s.setPending);
  const setCooldown = useAiChatStore((s) => s.setCooldown);

  const [draft, setDraft] = React.useState("");
  const [error, setError] = React.useState<ChatError | null>(null);
  const [mounted, setMounted] = React.useState(false);
  const [now, setNow] = React.useState(() => Date.now());
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const abortRef = React.useRef<AbortController | null>(null);

  const cooldownSeconds = cooldownUntil ? Math.max(0, Math.ceil((cooldownUntil - now) / 1000)) : 0;
  const isCoolingDown = cooldownSeconds > 0;
  const canSend =
    !pending && !isCoolingDown && draft.trim().length > 0 && draft.length <= MAX_CHARS;

  React.useEffect(() => {
    if (!cooldownUntil) return;
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [cooldownUntil]);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    if (!isOpen) return;
    inputRef.current?.focus();
  }, [isOpen]);

  React.useEffect(() => {
    if (!isOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        abortRef.current?.abort();
        close();
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, close]);

  async function submit(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || pending || isCoolingDown) return;
    setError(null);
    setDraft("");
    addMessage({
      id: `${Date.now()}-user`,
      role: "user",
      text: message,
    });
    setPending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await sendChatMessage({
        message,
        conversationId,
        locale,
        accessToken: status === "authenticated" ? session?.access_token : null,
        signal: controller.signal,
      });
      setConversationId(response.conversation_id);
      addMessage({
        id: `${Date.now()}-assistant`,
        role: "assistant",
        text: response.reply,
        cards: response.product_cards,
      });
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ApiError && cause.status === 429) {
        setCooldown(Date.now() + RATE_LIMIT_COOLDOWN_MS);
        setError("rateLimited");
      } else if (cause instanceof ApiError && cause.status === 503) {
        setError("unavailable");
      } else if (cause instanceof ApiError && cause.status === 0) {
        setError("timeout");
      } else {
        setError("generic");
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setPending(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit(draft);
    }
  }

  function handleNewConversation() {
    abortRef.current?.abort();
    newConversation();
    setError(null);
    setDraft("");
    inputRef.current?.focus();
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (isOpen ? close() : open())}
        aria-label={isOpen ? t("close") : t("open")}
        aria-expanded={isOpen}
        aria-controls="ai-chat-panel"
        data-testid="ai-chat-trigger"
        className="group relative inline-flex h-9 w-9 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
      >
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-lg bg-gradient-to-tr from-primary/0 via-primary/0 to-primary/0 opacity-0 blur-[6px] transition-all duration-300 group-hover:from-primary/60 group-hover:via-sky-400/40 group-hover:to-accent/60 group-hover:opacity-100"
        />
        <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-primary/90 to-sky-500/90 text-primary-foreground shadow-sm transition-transform duration-300 ease-out group-hover:-translate-y-0.5 group-hover:scale-105">
          <RobotFaceIcon />
        </span>
      </button>

      {mounted && isOpen
        ? createPortal(
            <div
              id="ai-chat-panel"
              data-testid="ai-chat-panel"
              className={cn(
                "fixed z-[60] flex flex-col overflow-hidden rounded-2xl border border-white/10",
                "bg-ink text-white shadow-2xl shadow-black/40",
                "inset-x-2 bottom-2 top-16 sm:inset-x-auto sm:end-4 sm:top-auto sm:bottom-16 sm:h-[min(38rem,80vh)] sm:w-[24rem]",
              )}
            >
              <header className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/20 text-primary">
                  <Bot aria-hidden="true" className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold">{t("title")}</h2>
                  <p className="flex items-center gap-1.5 text-[11px] text-white/60">
                    <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    {t("online")}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("newConversation")}
                  onClick={handleNewConversation}
                  className="h-8 w-8 text-white/70 hover:bg-white/10 hover:text-white"
                >
                  <MessageSquarePlus aria-hidden="true" className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("close")}
                  onClick={() => {
                    abortRef.current?.abort();
                    close();
                    triggerRef.current?.focus();
                  }}
                  className="h-8 w-8 text-white/70 hover:bg-white/10 hover:text-white"
                >
                  <X aria-hidden="true" className="h-4 w-4" />
                </Button>
              </header>

              <p className="mx-3 mt-3 flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] leading-snug text-amber-100">
                <Sparkles
                  aria-hidden="true"
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300"
                />
                {t("disclaimer")}
              </p>

              <div
                role="log"
                aria-live="polite"
                aria-label={t("title")}
                data-testid="ai-chat-log"
                className="flex-1 space-y-3 overflow-y-auto px-3 py-3"
              >
                {messages.length === 0 && !pending ? (
                  <div className="space-y-2 pt-2">
                    {SUGGESTION_KEYS.map((key) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => void submit(t(key))}
                        className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-start text-xs text-white/75 transition-colors hover:bg-white/10 hover:text-white"
                      >
                        <Sparkles aria-hidden="true" className="h-3 w-3 text-primary" />
                        {t(key)}
                      </button>
                    ))}
                  </div>
                ) : null}

                {messages.map((message) => (
                  <ChatBubble key={message.id} message={message} />
                ))}

                {pending ? (
                  <p
                    data-testid="ai-chat-typing"
                    className="flex items-center gap-1 px-1 text-[11px] text-white/60"
                  >
                    <span className="sr-only">{t("typing")}</span>
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/50 [animation-delay:0ms]"
                    />
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/50 [animation-delay:120ms]"
                    />
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/50 [animation-delay:240ms]"
                    />
                  </p>
                ) : null}

                {error ? (
                  <div
                    data-testid="ai-chat-error"
                    role="alert"
                    className="rounded-xl border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-100"
                  >
                    {error === "rateLimited" && isCoolingDown
                      ? t("errors.rateLimited", { seconds: cooldownSeconds })
                      : t(`errors.${error}`)}
                    {error === "unavailable" ? (
                      <Link href="/catalog" className="ms-1 underline underline-offset-2">
                        {t("goToCatalog")}
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="border-t border-white/10 p-3">
                <label htmlFor="ai-chat-input" className="sr-only">
                  {t("placeholder")}
                </label>
                <div className="flex items-end gap-2">
                  <textarea
                    id="ai-chat-input"
                    ref={inputRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value.slice(0, MAX_CHARS))}
                    onKeyDown={handleKeyDown}
                    placeholder={t("placeholder")}
                    maxLength={MAX_CHARS}
                    rows={2}
                    aria-describedby="ai-chat-counter"
                    className="max-h-28 min-h-[2.5rem] flex-1 resize-none rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  />
                  <Button
                    type="button"
                    size="icon"
                    aria-label={t("send")}
                    disabled={!canSend}
                    onClick={() => void submit(draft)}
                    className="h-9 w-9 shrink-0 rounded-xl"
                  >
                    <Send aria-hidden="true" className="h-4 w-4" />
                  </Button>
                </div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-white/45">
                  <span id="ai-chat-counter" data-testid="ai-chat-counter">
                    {t("counter", { count: MAX_CHARS - draft.length, max: MAX_CHARS })}
                  </span>
                  <span>{t("enterHint")}</span>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function RobotFaceIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      data-testid="ai-chat-robot-face"
    >
      <circle cx="12" cy="2.4" r="1" fill="currentColor" stroke="none" />
      <line x1="12" y1="3.4" x2="12" y2="5.4" />
      <rect x="3.6" y="5.4" width="16.8" height="12.6" rx="4.2" />
      <line x1="2" y1="11" x2="3.6" y2="11" />
      <line x1="20.4" y1="11" x2="22" y2="11" />
      {/* Olhos: piscam juntos no hover do gatilho (keyframes ai-blink). */}
      <g className="ai-eyes group-hover:[animation:ai-blink_0.7s_ease-in-out_1]">
        <line x1="9" y1="10.6" x2="9" y2="12.4" strokeWidth="2.1" />
        <line x1="15" y1="10.6" x2="15" y2="12.4" strokeWidth="2.1" />
      </g>
      <path d="M9.4 15.6h5.2" />
    </svg>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[92%] space-y-2", isUser ? "items-end" : "items-start")}>
        {/* Texto SEMPRE puro: sem HTML/Markdown, sem links vindos do modelo. */}
        <p
          data-testid={`ai-chat-message-${message.role}`}
          className={cn(
            "whitespace-pre-line rounded-2xl px-3 py-2 text-sm leading-relaxed",
            isUser ? "bg-primary text-primary-foreground" : "bg-white/8 text-white/90",
          )}
        >
          {message.text}
        </p>
        {message.cards && message.cards.length > 0 ? (
          <ul data-testid="ai-chat-cards" className="space-y-2">
            {message.cards.map((card) => (
              <ChatProductCardView key={card.product_id} card={card} />
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
