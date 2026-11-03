"use client";

import * as React from "react";

interface TurnstileOptions {
  sitekey: string;
  language?: string;
  appearance?: "always" | "execute" | "interaction-only";
  theme?: "auto" | "light" | "dark";
  callback?: (token: string) => void;
  "expired-callback"?: () => void;
  "error-callback"?: () => void;
}

interface TurnstileApi {
  render: (container: HTMLElement, options: TurnstileOptions) => string;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let loader: Promise<void> | null = null;

function loadTurnstile(nonce?: string): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no_window"));
  if (window.turnstile) return Promise.resolve();
  if (loader) return loader;

  loader = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>("script[data-forja-turnstile]");
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("turnstile_script_failed")), {
        once: true,
      });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.dataset.forjaTurnstile = "true";
    if (nonce) script.nonce = nonce;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("turnstile_script_failed"));
    document.head.appendChild(script);
  });
  return loader;
}

interface TurnstileWidgetProps {
  siteKey?: string;
  nonce?: string;
  language: string;
  resetKey?: number;
  onToken: (token: string) => void;
  onError: () => void;
}

/**
 * Widget oficial do Cloudflare Turnstile carregado com nonce da CSP.
 *
 * O token e de uso unico; o pai remonta o widget com `resetKey` apos cada
 * tentativa. Sem site key, o componente nao renderiza e o pai bloqueia o envio.
 */
export function TurnstileWidget({
  siteKey,
  nonce,
  language,
  resetKey = 0,
  onToken,
  onError,
}: TurnstileWidgetProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const onTokenRef = React.useRef(onToken);
  const onErrorRef = React.useRef(onError);
  onTokenRef.current = onToken;
  onErrorRef.current = onError;

  React.useEffect(() => {
    if (!siteKey) {
      onErrorRef.current();
      return;
    }
    let cancelled = false;
    let widgetId: string | null = null;

    void loadTurnstile(nonce)
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        widgetId = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          language,
          appearance: "always",
          theme: "auto",
          callback: (token) => {
            if (!cancelled) onTokenRef.current(token);
          },
          "expired-callback": () => {
            if (!cancelled) onErrorRef.current();
          },
          "error-callback": () => {
            if (!cancelled) onErrorRef.current();
          },
        });
      })
      .catch(() => {
        if (!cancelled) onErrorRef.current();
      });

    return () => {
      cancelled = true;
      if (widgetId && window.turnstile) {
        window.turnstile.remove(widgetId);
      }
    };
  }, [siteKey, nonce, language, resetKey]);

  if (!siteKey) return null;
  return <div ref={containerRef} className="min-h-[65px]" />;
}
