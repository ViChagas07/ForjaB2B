// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAiChatStore } from "@/features/ai-chat/store";
import { AiChatWidget } from "@/features/ai-chat/ai-chat-widget";
import { ApiError } from "@/infrastructure/http/errors";

const pushMock = vi.fn();
const sendChatMessageMock = vi.fn();
const getLlmHealthMock = vi.fn();
const { pathnameMock } = vi.hoisted(() => ({ pathnameMock: vi.fn(() => "/") }));

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    locale: _locale,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    locale?: string;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
  useRouter: () => ({ push: pushMock, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: pathnameMock,
}));

vi.mock("@/infrastructure/http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/infrastructure/http")>();
  return {
    ...actual,
    sendChatMessage: (...args: unknown[]) => sendChatMessageMock(...args),
    getLlmHealth: (...args: unknown[]) => getLlmHealthMock(...args),
  };
});

vi.mock("@/shared/components/product-image", () => ({
  ProductImage: ({ src, alt }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} />
  ),
}));

vi.mock("@/features/catalog", async () => {
  const { useTranslations } = await import("next-intl");
  function MockCatalogPrice({
    amount,
    priceOnRequest,
  }: {
    amount: string | null;
    priceOnRequest: boolean;
  }) {
    const t = useTranslations();
    return <span>{priceOnRequest || !amount ? t("catalog.priceOnRequest") : `R$ ${amount}`}</span>;
  }
  function MockCaStatusBadge() {
    const t = useTranslations();
    return <span>{t("catalog.caValid")}</span>;
  }
  return { CatalogPrice: MockCatalogPrice, CaStatusBadge: MockCaStatusBadge };
});

vi.mock("@/features/cart/hooks", () => ({
  useAddCartItem: () => ({ mutate: vi.fn(), isPending: false }),
}));

import type { AbstractIntlMessages } from "next-intl";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function widgetTree(locale = "pt-BR") {
  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <AiChatWidget />
    </NextIntlClientProvider>
  );
}

function renderWidget(locale = "pt-BR") {
  return render(widgetTree(locale));
}

const CARD = {
  product_id: "11111111-1111-4111-8111-111111111111",
  name: "Capacete para Soldador",
  sku: "CAP-001",
  image_url: "/images/cap.png",
  image_alt: "Capacete",
  link: "/catalog/11111111-1111-4111-8111-111111111111",
  price: null,
  currency: "BRL",
  price_on_request: true,
  min_order_qty: 1,
  ca_status: "VALID",
};

beforeEach(() => {
  useAiChatStore.getState().reset();
  pushMock.mockReset();
  sendChatMessageMock.mockReset();
  getLlmHealthMock.mockReset();
  pathnameMock.mockReturnValue("/");
  getLlmHealthMock.mockResolvedValue({ available: true, enabled: true, model: "qwen/qwen3.5-9b" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function openWidget() {
  renderWidget();
  fireEvent.click(screen.getByTestId("ai-chat-trigger"));
  return screen.getByTestId("ai-chat-panel");
}

describe("AiChatWidget", () => {
  it("abre pelo gatilho do navbar, mostra boas-vindas e fecha com Esc devolvendo o foco", () => {
    const panel = openWidget();
    expect(panel).toBeTruthy();
    expect(screen.getByTestId("ai-chat-robot-face")).toBeTruthy();
    expect(screen.getByTestId("ai-chat-robot-face").querySelector(".ai-eyes")).toBeTruthy();
    expect(screen.getByText(/Seja bem-vindo ao ForjaB2B/i)).toBeTruthy();
    expect(screen.getByRole("log")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("ai-chat-panel")).toBeNull();
    expect(document.activeElement).toBe(screen.getByTestId("ai-chat-trigger"));
  });

  it("limita a 500 caracteres e mostra o contador", () => {
    openWidget();
    const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
    fireEvent.change(input, { target: { value: "x".repeat(600) } });
    expect((input as HTMLTextAreaElement).value.length).toBe(500);
    expect(screen.getByTestId("ai-chat-counter").textContent).toContain("0 de 500");
  });

  it("Enter envia e Shift+Enter não envia", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversation_id: "22222222-2222-4222-8222-222222222222",
      reply: "Resposta curta.",
      product_cards: [],
    });
    openWidget();
    const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
    fireEvent.change(input, { target: { value: "capacete" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(sendChatMessageMock).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(sendChatMessageMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Resposta curta.")).toBeTruthy();
  });

  it("renderiza a resposta como TEXTO PURO (sem HTML injetado)", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversation_id: "22222222-2222-4222-8222-222222222222",
      reply: '<img src=x onerror="alert(1)"><script>alert(2)</script>',
      product_cards: [],
    });
    openWidget();
    fireEvent.change(screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho..."), {
      target: { value: "oi" },
    });
    fireEvent.keyDown(screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho..."), {
      key: "Enter",
    });
    await waitFor(() => expect(screen.getByTestId("ai-chat-message-assistant")).toBeTruthy());
    expect(screen.getByTestId("ai-chat-message-assistant").textContent).toContain("<img");
    expect(screen.getByTestId("ai-chat-log").querySelector("img")).toBeNull();
    expect(screen.getByTestId("ai-chat-log").querySelector("script")).toBeNull();
  });

  it("mostra cartões do backend com link e preço consultivo", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversation_id: "22222222-2222-4222-8222-222222222222",
      reply: "Veja o cartão.",
      product_cards: [CARD],
    });
    openWidget();
    const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
    fireEvent.change(input, { target: { value: "capacete para soldador" } });
    fireEvent.keyDown(input, { key: "Enter" });
    const link = await screen.findByRole("link", { name: "Ver produto" });
    expect(link.getAttribute("href")).toBe(`/catalog/${CARD.product_id}`);
    expect(screen.getAllByText(/sob consulta/i).length).toBeGreaterThan(0);
  });

  it("429 mostra mensagem neutra e desabilita o envio até o Retry-After", async () => {
    sendChatMessageMock.mockRejectedValue(
      new ApiError({
        type: "urn:forja:problem:http_429",
        title: "Too Many Requests",
        status: 429,
      }),
    );
    openWidget();
    const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
    fireEvent.change(input, { target: { value: "oi" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByTestId("ai-chat-error")).toBeTruthy();
    fireEvent.change(input, { target: { value: "de novo" } });
    const send = screen.getByRole("button", { name: "Enviar mensagem" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
  });

  it("503 mostra assistente indisponível com link para o catálogo", async () => {
    sendChatMessageMock.mockRejectedValue(
      new ApiError({
        type: "urn:forja:problem:http_503",
        title: "Service Unavailable",
        status: 503,
      }),
    );
    openWidget();
    const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
    fireEvent.change(input, { target: { value: "oi" } });
    expect(useAiChatStore.getState().cooldownUntil).toBeNull();
    expect(useAiChatStore.getState().pending).toBe(false);
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("ai-chat-log").textContent).toContain("oi"));
    const box = await screen.findByTestId("ai-chat-error");
    expect(box.textContent).toMatch(/indispon/i);
    expect(screen.getByRole("link", { name: /catálogo/i }).getAttribute("href")).toBe("/catalog");
  });
});

it("mostra modo catálogo quando /health/llm está indisponível", async () => {
  getLlmHealthMock.mockResolvedValue({ available: false, enabled: true, model: "qwen/qwen3.5-9b" });
  openWidget();
  const banner = await screen.findByTestId("ai-chat-demo");
  expect(banner.textContent).toMatch(/modo catálogo/i);
  expect(screen.getByRole("link", { name: /README/i }).getAttribute("href")).toContain(
    "github.com/ViChagas07/ForjaB2B",
  );
});

it("aplica lang/dir e rotulos do cartao na bolha arabe em site pt-BR", async () => {
  sendChatMessageMock.mockResolvedValue({
    conversation_id: "22222222-2222-4222-8222-222222222222",
    reply: "مرحباً! هذه لفات.",
    product_cards: [CARD],
    language: "ar",
  });
  openWidget();
  expect(
    screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...").getAttribute("dir"),
  ).toBe("auto");
  const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
  fireEvent.change(input, { target: { value: "مرحبا" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("مرحباً! هذه لفات.");
  expect(screen.getByTestId("ai-chat-message-user").getAttribute("lang")).toBe("ar");
  expect(screen.getByTestId("ai-chat-message-user").getAttribute("dir")).toBe("rtl");
  expect(screen.getByTestId("ai-chat-message-assistant").getAttribute("lang")).toBe("ar");
  expect(screen.getByTestId("ai-chat-message-assistant").getAttribute("dir")).toBe("rtl");
  expect(screen.getByTestId("ai-chat-cards").getAttribute("dir")).toBe("rtl");
  expect(screen.getByTestId("ai-chat-cards").getAttribute("lang")).toBe("ar");
  expect(screen.getByText(/السعر عند الطلب/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "عرض المنتج" })).toBeTruthy();
});

it("aplica lang/dir e rotulos japoneses na bolha em site pt-BR", async () => {
  sendChatMessageMock.mockResolvedValue({
    conversation_id: "22222222-2222-4222-8222-222222222222",
    reply: "こんにちは! 手袋です。",
    product_cards: [CARD],
    language: "ja",
  });
  openWidget();
  const input = screen.getByLabelText("Pergunte sobre produtos, frete ou seu carrinho...");
  fireEvent.change(input, { target: { value: "こんにちは" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("こんにちは! 手袋です。");
  expect(screen.getByTestId("ai-chat-message-user").getAttribute("lang")).toBe("ja");
  expect(screen.getByTestId("ai-chat-message-user").getAttribute("dir")).toBe("ltr");
  expect(screen.getByTestId("ai-chat-message-assistant").getAttribute("lang")).toBe("ja");
  expect(screen.getByTestId("ai-chat-message-assistant").getAttribute("dir")).toBe("ltr");
  expect(screen.getByTestId("ai-chat-cards").getAttribute("dir")).toBe("ltr");
  expect(screen.getByText(/価格はお問い合わせください/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "商品を見る" })).toBeTruthy();
});

describe("fechamento por clique fora e reset de conversa", () => {
  function seedConversation() {
    useAiChatStore.setState({
      conversationId: "conv-1",
      messages: [{ id: "1", role: "user", text: "oi" }],
      pending: true,
    });
  }

  it("fecha ao clicar fora e mantem aberto ao clicar dentro", () => {
    openWidget();
    fireEvent.pointerDown(screen.getByTestId("ai-chat-log"));
    expect(screen.getByTestId("ai-chat-panel")).toBeTruthy();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByTestId("ai-chat-panel")).toBeNull();
  });

  it("limpa a conversa ao esconder a aba do navegador", async () => {
    openWidget();
    seedConversation();
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
    await waitFor(() => {
      expect(useAiChatStore.getState().messages).toHaveLength(0);
      expect(useAiChatStore.getState().conversationId).toBeNull();
      expect(useAiChatStore.getState().pending).toBe(false);
    });
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
  });

  it("limpa a conversa no pagehide (refresh/navegacao)", async () => {
    openWidget();
    seedConversation();
    window.dispatchEvent(new Event("pagehide"));
    await waitFor(() => {
      expect(useAiChatStore.getState().messages).toHaveLength(0);
      expect(useAiChatStore.getState().conversationId).toBeNull();
    });
  });

  it("limpa a conversa quando o idioma muda", async () => {
    const view = renderWidget();
    fireEvent.click(screen.getByTestId("ai-chat-trigger"));
    seedConversation();
    view.rerender(widgetTree("en"));
    await waitFor(() => {
      expect(useAiChatStore.getState().messages).toHaveLength(0);
      expect(useAiChatStore.getState().conversationId).toBeNull();
    });
  });

  it("limpa a conversa quando o pathname/aba muda", async () => {
    const view = renderWidget();
    fireEvent.click(screen.getByTestId("ai-chat-trigger"));
    seedConversation();
    pathnameMock.mockReturnValue("/catalog");
    view.rerender(widgetTree());
    await waitFor(() => {
      expect(useAiChatStore.getState().messages).toHaveLength(0);
      expect(useAiChatStore.getState().conversationId).toBeNull();
    });
  });
});
