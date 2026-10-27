import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createDebouncer } from "@/features/search/debounce";
import { searchKeys } from "@/features/search/query-keys";
import {
  SUGGEST_STALE_TIME_MS,
  suggestQueryOptions,
} from "@/features/search/use-search-suggestions";
import { searchApi } from "@/infrastructure/http";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("createDebouncer (fake timers)", () => {
  it("executa somente a última tarefa após o delay", () => {
    vi.useFakeTimers();
    const debouncer = createDebouncer(200);
    const run = vi.fn();

    debouncer(run);
    vi.advanceTimersByTime(199);
    expect(run).not.toHaveBeenCalled();

    debouncer(run); // nova tecla: reinicia o timer
    vi.advanceTimersByTime(199);
    expect(run).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("cancelamento impede a tarefa pendente", () => {
    vi.useFakeTimers();
    const debouncer = createDebouncer(200);
    const run = vi.fn();

    const cancel = debouncer(run);
    cancel();
    vi.advanceTimersByTime(1_000);

    expect(run).not.toHaveBeenCalled();
  });
});

describe("searchApi.fetchSuggestions", () => {
  it("chama GET /api/v1/search/suggest com q e Accept-Language", async () => {
    const body = { terms: [], categories: [], products: [], query: "cap" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchApi.fetchSuggestions("cap", "pt-BR");

    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/search/suggest?q=cap");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["Accept-Language"]).toBe("pt-BR");
  });

  it("repassa o cancelamento do signal como AbortError (não ApiError)", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const external = new AbortController();
    const pending = searchApi.fetchSuggestions("cap", "en", external.signal);
    external.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("suggestQueryOptions", () => {
  it("desabilita com menos de 2 caracteres após trim", () => {
    expect(suggestQueryOptions("pt-BR", "a").enabled).toBe(false);
    expect(suggestQueryOptions("pt-BR", "  a  ").enabled).toBe(false);
    expect(suggestQueryOptions("pt-BR", "ca").enabled).toBe(true);
  });

  it("configura staleTime, retry desativado e placeholderData do anterior", () => {
    const options = suggestQueryOptions("en", "cap");
    expect(options.staleTime).toBe(SUGGEST_STALE_TIME_MS);
    expect(options.retry).toBe(false);
    const previous = { terms: [], categories: [], products: [], query: "ca" };
    expect(options.placeholderData?.(previous, undefined)).toBe(previous);
  });

  it("consulta o termo com trim e repassa o signal do contexto", async () => {
    const body = { terms: [], categories: [], products: [], query: "cap" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const options = suggestQueryOptions("pt-BR", " cap ");
    expect(options.queryKey).toEqual(["search", "suggestions", "pt-BR", "cap"]);
    await options.queryFn?.({
      client: new QueryClient(),
      signal: new AbortController().signal,
      meta: {},
    });

    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("q=cap");
  });
});

describe("searchKeys (cache por idioma e termo normalizado)", () => {
  it("separa entradas por locale", () => {
    expect(searchKeys.suggestions("pt-BR", "cap")).not.toEqual(searchKeys.suggestions("en", "cap"));
  });

  it("normaliza trim e lowercase para reusar o cache", () => {
    expect(searchKeys.suggestions("en", "  CAP ")).toEqual(searchKeys.suggestions("en", "cap"));
  });

  it("invalidação por prefixo encontra todas as sugestões", () => {
    const client = new QueryClient();
    client.setQueryData(searchKeys.suggestions("pt-BR", "cap"), { terms: [] });
    client.setQueryData(searchKeys.suggestions("en", "cap"), { terms: [] });

    expect(client.getQueryCache().findAll({ queryKey: ["search", "suggestions"] })).toHaveLength(2);
  });
});

describe("integração QueryClient", () => {
  it("fetchQuery executa as opções do suggest de ponta a ponta", async () => {
    const body = {
      terms: [{ text: "Capacete", kind: "product" as const }],
      categories: [],
      products: [],
      query: "cap",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    const client = new QueryClient();
    const result = await client.fetchQuery(suggestQueryOptions("pt-BR", "cap"));

    expect(result.terms).toEqual([{ text: "Capacete", kind: "product" }]);
  });
});
