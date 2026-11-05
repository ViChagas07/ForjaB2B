"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { Bot, MessageSquarePlus, Send, Sparkles, X } from "lucide-react";
import { NextIntlClientProvider, useLocale, useTranslations } from "next-intl";

import { useAuthStore } from "@/shared/stores/auth-store";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { defaultLocale, directionForLocale, isLocale, type Locale } from "@/i18n/locales";
import { Link, usePathname } from "@/i18n/navigation";
import { ApiError, getLlmHealth, sendChatMessage, type LlmHealth } from "@/infrastructure/http";

import { CHAT_CARD_MESSAGES } from "./card-messages";
import { ChatProductCardView } from "./product-card";
import { type ChatMessage, useAiChatStore } from "./store";

const MAX_CHARS = 500;
const RATE_LIMIT_COOLDOWN_MS = 30_000;
const SUGGESTION_KEYS = ["suggestion1", "suggestion2", "suggestion3"] as const;
const AI_DEMO_URL =
  process.env.NEXT_PUBLIC_AI_DEMO_URL ??
  "https://github.com/ViChagas07/ForjaB2B#rodando-a-ia-localmente-com-lm-studio";

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
  const pathname = usePathname();
  const siteLocale: Locale = isLocale(locale) ? locale : defaultLocale;
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
  const setMessageLanguage = useAiChatStore((s) => s.setMessageLanguage);
  const setPending = useAiChatStore((s) => s.setPending);
  const setCooldown = useAiChatStore((s) => s.setCooldown);

  const [draft, setDraft] = React.useState("");
  const [error, setError] = React.useState<ChatError | null>(null);
  const [mounted, setMounted] = React.useState(false);
  const [now, setNow] = React.useState(() => Date.now());
  const [llmHealth, setLlmHealth] = React.useState<LlmHealth | null>(null);
  const [degraded, setDegraded] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const previousLocaleRef = React.useRef(siteLocale);
  const previousPathnameRef = React.useRef(pathname);

  const cooldownSeconds = cooldownUntil ? Math.max(0, Math.ceil((cooldownUntil - now) / 1000)) : 0;
  const isCoolingDown = cooldownSeconds > 0;
  const canSend =
    !pending && !isCoolingDown && draft.trim().length > 0 && draft.length <= MAX_CHARS;
  const demoMode = degraded || (llmHealth !== null && !llmHealth.available);

  const resetConversation = React.useCallback(() => {
    abortRef.current?.abort();
    newConversation();
    setError(null);
    setDraft("");
    setDegraded(false);
  }, [newConversation]);

  React.useEffect(() => {
    if (!cooldownUntil) return;
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [cooldownUntil]);

  React.useEffect(() => {
    if (previousLocaleRef.current === siteLocale) return;
    previousLocaleRef.current = siteLocale;
    resetConversation();
  }, [siteLocale, resetConversation]);

  React.useEffect(() => {
    if (previousPathnameRef.current === pathname) return;
    previousPathnameRef.current = pathname;
    resetConversation();
  }, [pathname, resetConversation]);

  React.useEffect(() => {
    function onVisibilityChange() {
      if (document.visibilityState === "hidden") resetConversation();
    }
    function onPageHide() {
      resetConversation();
    }
    function onPageShow(event: PageTransitionEvent) {
      if (event.persisted) resetConversation();
    }
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
    };
  }, [resetConversation]);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    // A troca de idioma via next-intl pode remontar o widget no novo layout
    // [locale]. Nesse caso os refs acima ja nascem com o valor novo; o store
    // global e que sobrevive. Se ha conversa, ela pertence ao mount anterior.
    const state = useAiChatStore.getState();
    if (state.messages.length > 0 || state.conversationId !== null) {
      resetConversation();
    }
  }, [resetConversation]);

  React.useEffect(() => {
    if (!isOpen) return;
    let active = true;
    void getLlmHealth().then((health) => {
      if (active) setLlmHealth(health);
    });
    return () => {
      active = false;
    };
  }, [isOpen]);

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

  React.useEffect(() => {
    if (!isOpen) return;
    function onPointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      abortRef.current?.abort();
      close();
    }
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => document.removeEventListener("pointerdown", onPointerDown, true);
  }, [isOpen, close]);

  async function submit(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || pending || isCoolingDown) return;
    setError(null);
    setDraft("");
    const userMessageId = `${Date.now()}-user`;
    addMessage({
      id: userMessageId,
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
      if (controller.signal.aborted) return;
      const responseLanguage: Locale =
        typeof response.language === "string" && isLocale(response.language)
          ? response.language
          : siteLocale;
      const languageMismatch = response.language_mismatch === true;
      const detectedLanguage: Locale | null =
        typeof response.detected_language === "string" && isLocale(response.detected_language)
          ? response.detected_language
          : null;
      setConversationId(response.conversation_id);
      setDegraded(Boolean(response.degraded));
      setMessageLanguage(
        userMessageId,
        languageMismatch && detectedLanguage ? detectedLanguage : responseLanguage,
      );
      if (!response.degraded && !languageMismatch) {
        // Se o health estava em cache como indisponivel (backend/modelo
        // acabou de subir), uma resposta real bem-sucedida limpa o aviso.
        setLlmHealth((previous) => ({
          available: true,
          enabled: true,
          model: previous?.model ?? "",
        }));
        void getLlmHealth(true).then(setLlmHealth);
      }
      addMessage({
        id: `${Date.now()}-assistant`,
        role: "assistant",
        text: response.reply,
        language: responseLanguage,
        cards: response.product_cards,
        warning: languageMismatch,
      });
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ApiError && cause.status === 429) {
        setCooldown(Date.now() + RATE_LIMIT_COOLDOWN_MS);
        setError("rateLimited");
      } else if (cause instanceof ApiError && cause.status === 503) {
        setLlmHealth({ available: false, enabled: false, model: "" });
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
    resetConversation();
    void getLlmHealth(true).then(setLlmHealth);
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
          className="absolute inset-0 rounded-lg bg-gradient-to-tr from-white/0 via-primary/0 to-ink/0 opacity-0 blur-[6px] transition-all duration-300 group-hover:from-white/50 group-hover:via-primary/60 group-hover:to-ink/50 group-hover:opacity-100"
        />
        <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#FFFFFF_0%,#FFFFFF_20%,#F59E0B_55%,#0A0A0A_100%)] text-ink shadow-sm transition-transform duration-300 ease-out group-hover:-translate-y-0.5 group-hover:scale-105">
          <RobotFaceIcon />
        </span>
      </button>

      {mounted && isOpen
        ? createPortal(
            <div
              id="ai-chat-panel"
              ref={panelRef}
              data-testid="ai-chat-panel"
              className={cn(
                "fixed z-[60] flex flex-col overflow-hidden rounded-2xl border border-border",
                "bg-background text-foreground shadow-2xl shadow-black/20",
                "dark:border-white/10 dark:bg-ink dark:text-white dark:shadow-black/40",
                "inset-x-2 bottom-2 top-16 sm:inset-x-auto sm:end-4 sm:top-auto sm:bottom-16 sm:h-[min(38rem,80vh)] sm:w-[24rem]",
              )}
            >
              <header className="flex items-center gap-3 border-b border-border px-4 py-3 dark:border-white/10">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/20 text-primary">
                  <Bot aria-hidden="true" className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold">{t("title")}</h2>
                  <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground dark:text-white/60">
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400"
                    />
                    {t("online")}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("newConversation")}
                  onClick={handleNewConversation}
                  className="h-8 w-8 text-muted-foreground hover:bg-muted hover:text-foreground dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white"
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
                  className="h-8 w-8 text-muted-foreground hover:bg-muted hover:text-foreground dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white"
                >
                  <X aria-hidden="true" className="h-4 w-4" />
                </Button>
              </header>

              <p className="mx-3 mt-3 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-snug text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100">
                <Sparkles
                  aria-hidden="true"
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-300"
                />
                {t("disclaimer")}
              </p>

              {demoMode ? (
                <p
                  data-testid="ai-chat-demo"
                  className="mx-3 mt-2 rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-[11px] leading-snug text-sky-900 dark:border-sky-400/30 dark:bg-sky-400/10 dark:text-sky-100"
                >
                  {t("demoMode")}{" "}
                  <a
                    href={AI_DEMO_URL}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="underline underline-offset-2"
                  >
                    {t("demoModeLink")}
                  </a>
                </p>
              ) : null}

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
                        className="flex w-full items-center gap-2 rounded-xl border border-border px-3 py-2 text-start text-xs text-foreground/75 transition-colors hover:bg-muted hover:text-foreground dark:border-white/10 dark:text-white/75 dark:hover:bg-white/10 dark:hover:text-white"
                      >
                        <Sparkles aria-hidden="true" className="h-3 w-3 text-primary" />
                        {t(key)}
                      </button>
                    ))}
                  </div>
                ) : null}

                {messages.map((message) => (
                  <ChatBubble key={message.id} message={message} siteLocale={siteLocale} />
                ))}

                {pending ? (
                  <p
                    data-testid="ai-chat-typing"
                    className="flex items-center gap-1 px-1 text-[11px] text-muted-foreground dark:text-white/60"
                  >
                    <span className="sr-only">{t("typing")}</span>
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 dark:bg-white/50 [animation-delay:0ms]"
                    />
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 dark:bg-white/50 [animation-delay:120ms]"
                    />
                    <span
                      aria-hidden="true"
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 dark:bg-white/50 [animation-delay:240ms]"
                    />
                  </p>
                ) : null}

                {error ? (
                  <div
                    data-testid="ai-chat-error"
                    role="alert"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-900 dark:border-red-400/30 dark:bg-red-400/10 dark:text-red-100"
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

              <div className="border-t border-border p-3 dark:border-white/10">
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
                    dir="auto"
                    maxLength={MAX_CHARS}
                    rows={2}
                    aria-describedby="ai-chat-counter"
                    className="max-h-28 min-h-[2.5rem] flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary dark:border-white/15 dark:bg-white/5 dark:text-white dark:placeholder:text-white/40"
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
                <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground dark:text-white/45">
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

function ChatBubble({ message, siteLocale }: { message: ChatMessage; siteLocale: Locale }) {
  const isUser = message.role === "user";
  const messageLocale = message.language ?? siteLocale;
  const dir = directionForLocale(messageLocale);
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[92%] space-y-2", isUser ? "items-end" : "items-start")}>
        {/* Texto SEMPRE puro: sem HTML/Markdown, sem links vindos do modelo. */}
        {message.warning ? (
          <div
            data-testid="ai-chat-language-alert"
            role="alert"
            lang={message.language}
            dir={message.language ? dir : "auto"}
            className="whitespace-pre-line rounded-2xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm leading-relaxed text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100"
          >
            {message.text}
          </div>
        ) : (
          <p
            data-testid={`ai-chat-message-${message.role}`}
            lang={message.language}
            dir={message.language ? dir : "auto"}
            className={cn(
              "whitespace-pre-line rounded-2xl px-3 py-2 text-sm leading-relaxed",
              isUser
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground dark:bg-white/8 dark:text-white/90",
            )}
          >
            {message.text}
          </p>
        )}
        {message.cards && message.cards.length > 0 ? (
          <ul data-testid="ai-chat-cards" lang={messageLocale} dir={dir} className="space-y-2">
            <NextIntlClientProvider
              locale={messageLocale}
              messages={CHAT_CARD_MESSAGES[messageLocale]}
              timeZone="UTC"
            >
              {message.cards.map((card) => (
                <ChatProductCardView key={card.product_id} card={card} siteLocale={siteLocale} />
              ))}
            </NextIntlClientProvider>
          </ul>
        ) : null}
      </div>
    </div>
  );
}
