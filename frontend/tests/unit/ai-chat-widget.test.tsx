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

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
  useRouter: () => ({ push: pushMock, replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/infrastructure/http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/infrastructure/http")>();
  return {
    ...actual,
    sendChatMessage: (...args: unknown[]) => sendChatMessageMock(...args),
  };
});

vi.mock("@/shared/components/product-image", () => ({
  ProductImage: ({ src, alt }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} />
  ),
}));

vi.mock("@/features/catalog", () => ({
  CatalogPrice: ({
    amount,
    priceOnRequest,
  }: {
    amount: string | null;
    priceOnRequest: boolean;
  }) => <span>{priceOnRequest || !amount ? "sob consulta" : `R$ ${amount}`}</span>,
  CaStatusBadge: () => <span>CA</span>,
}));

vi.mock("@/features/cart/hooks", () => ({
  useAddCartItem: () => ({ mutate: vi.fn(), isPending: false }),
}));

import type { AbstractIntlMessages } from "next-intl";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderWidget() {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <AiChatWidget />
    </NextIntlClientProvider>,
  );
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
  it("abre pelo gatilho do navbar, mostra aviso de IA e fecha com Esc devolvendo o foco", () => {
    const panel = openWidget();
    expect(panel).toBeTruthy();
    expect(screen.getByTestId("ai-chat-robot-face")).toBeTruthy();
    expect(screen.getByTestId("ai-chat-robot-face").querySelector(".ai-eyes")).toBeTruthy();
    expect(screen.getByText(/assistente de IA/i)).toBeTruthy();
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
    expect(screen.getAllByText("sob consulta").length).toBeGreaterThan(0);
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
