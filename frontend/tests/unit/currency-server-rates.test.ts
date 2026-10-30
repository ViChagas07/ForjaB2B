import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import {
  FX_RATES_REVALIDATE_SECONDS,
  FX_RATES_TAG,
  getFxRatesForServer,
} from "@/features/currency/server-rates";

type FetchInitWithNext = RequestInit & {
  next?: { revalidate?: number; tags?: string[] };
};

const PAYLOAD = {
  base: "BRL",
  rates: {
    BRL: "1",
    USD: "0.18408",
    EUR: "0.16477",
    GBP: "0.13738",
    CAD: "0.25713",
    AUD: "0.26204",
    JPY: "28.946",
    CNY: "1.2246",
    CHF: "0.15149",
  },
  rate_date: "2026-10-30",
  fetched_at: "2026-10-30T23:00:00Z",
  source: "Frankfurter / European Central Bank",
  stale: false,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function callOf(fetchMock: Mock): { url: string; init: FetchInitWithNext } {
  const call = fetchMock.mock.calls[0];
  if (!call) throw new Error("fetch nao foi chamado");
  return { url: String(call[0]), init: call[1] as FetchInitWithNext };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getFxRatesForServer", () => {
  it("busca a URL fixa com cache de 12h, sem cookies nem Authorization", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await getFxRatesForServer();

    expect(snapshot).not.toBeNull();
    expect(snapshot?.rates.USD).toBe("0.18408");
    expect(snapshot?.rates).not.toHaveProperty("CHF");
    expect(snapshot?.rateDate).toBe("2026-10-30");
    expect(snapshot?.source).toBe("Frankfurter / European Central Bank");
    expect(snapshot?.stale).toBe(false);

    const { url, init } = callOf(fetchMock);
    expect(url).toBe("https://forjab2b.onrender.com/api/v1/fx/rates");
    expect(url).not.toContain("?");
    expect(init.credentials).toBe("omit");
    expect(init.next?.revalidate).toBe(FX_RATES_REVALIDATE_SECONDS);
    expect(init.next?.revalidate).toBe(43_200);
    expect(init.next?.tags).toContain(FX_RATES_TAG);
    const headers = init.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBeUndefined();
    expect(headers?.Cookie).toBeUndefined();
  });

  it("HTTP de erro devolve null para a aplicacao seguir em BRL", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ detail: "x" }, 503)),
    );

    await expect(getFxRatesForServer()).resolves.toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  it("falha de rede devolve null sem lancar", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("network down")));

    await expect(getFxRatesForServer()).resolves.toBeNull();
  });

  it("payload invalido devolve null", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ base: "EUR", rates: {} })),
    );

    await expect(getFxRatesForServer()).resolves.toBeNull();
  });
});
