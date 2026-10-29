// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useProducts } from "@/features/catalog/hooks";
import { createQueryClient } from "@/shared/lib/query-client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("hooks do catálogo", () => {
  it("repassa o AbortSignal do React Query e cancela o fetch ao desmontar", async () => {
    const queryClient = createQueryClient();
    function wrapper({ children }: { children: React.ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>
          <NextIntlClientProvider locale="pt-BR" messages={{}}>
            {children}
          </NextIntlClientProvider>
        </QueryClientProvider>
      );
    }

    let capturedSignal: AbortSignal | undefined;
    const fetchMock = vi.fn<typeof fetch>((_input, init) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { unmount } = renderHook(() => useProducts({ page_size: 50 }), { wrapper });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(capturedSignal).toBeInstanceOf(AbortSignal);

    unmount();
    await waitFor(() => expect(capturedSignal?.aborted).toBe(true));
  });
});
