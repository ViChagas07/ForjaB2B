import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { cartKey } from "@/features/cart/hooks";
import { catalogKeys } from "@/features/catalog/query-keys";
import { orderKey } from "@/features/ordering/hooks";

describe("cache por idioma", () => {
  it("inclui o locale nas chaves de catálogo, carrinho e pedido", () => {
    expect(catalogKeys.product("pt-BR", "p1")).not.toEqual(catalogKeys.product("en", "p1"));
    expect(catalogKeys.products("pt-BR", { q: "x" })).not.toEqual(
      catalogKeys.products("en", { q: "x" }),
    );
    expect(cartKey("pt-BR")).not.toEqual(cartKey("ar"));
    expect(orderKey("o1", "pt-BR")).not.toEqual(orderKey("o1", "en"));
  });

  it("guarda respostas de idiomas diferentes em entradas diferentes", () => {
    const client = new QueryClient();
    client.setQueryData(catalogKeys.product("pt-BR", "p1"), { name: "Capacete" });
    client.setQueryData(catalogKeys.product("en", "p1"), { name: "Helmet" });

    expect(client.getQueryData(catalogKeys.product("pt-BR", "p1"))).toEqual({
      name: "Capacete",
    });
    expect(client.getQueryData(catalogKeys.product("en", "p1"))).toEqual({ name: "Helmet" });
  });

  it("mantém invalidação ampla por prefixo", () => {
    const client = new QueryClient();
    client.setQueryData(cartKey("pt-BR"), { items: [] });
    client.setQueryData(cartKey("en"), { items: [] });
    client.setQueryData(orderKey("o1", "en"), { id: "o1" });

    expect(client.getQueryCache().findAll({ queryKey: ["cart"] })).toHaveLength(2);
    expect(client.getQueryCache().findAll({ queryKey: ["orders"] })).toHaveLength(1);
  });
});
