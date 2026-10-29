import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogKeys } from "@/features/catalog/query-keys";
import { createQueryClient, getQueryClient } from "@/shared/lib/query-client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("QueryClient", () => {
  it("usa os defaults de performance do catálogo", () => {
    const defaults = createQueryClient().getDefaultOptions().queries;

    expect(defaults?.staleTime).toBe(5 * 60_000);
    expect(defaults?.gcTime).toBe(30 * 60_000);
    expect(defaults?.refetchOnWindowFocus).toBe(false);
    expect(defaults?.retry).toBe(1);
  });

  it("deduplica chamadas concorrentes e reaproveita o cache do catálogo", async () => {
    const client = createQueryClient();
    const queryFn = vi.fn<() => Promise<string[]>>().mockResolvedValue(["capacete"]);
    const options = {
      queryKey: catalogKeys.categories("pt-BR"),
      queryFn,
    };

    await Promise.all([client.fetchQuery(options), client.fetchQuery(options)]);
    expect(queryFn).toHaveBeenCalledTimes(1);

    await client.fetchQuery(options);
    expect(queryFn).toHaveBeenCalledTimes(1);
  });

  it("cria um cliente novo por requisição no servidor", () => {
    const first = getQueryClient();
    const second = getQueryClient();

    expect(first).not.toBe(second);
  });

  it("reutiliza um singleton no navegador", () => {
    vi.stubGlobal("window", {});

    expect(getQueryClient()).toBe(getQueryClient());
  });
});
