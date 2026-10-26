import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { ProductImage } from "@/shared/components/product-image";

const API = "http://localhost:8000";

describe("ProductImage (renderizacao estatica)", () => {
  it("foto (/catalog/photos) renderiza com object-cover e origem do frontend", () => {
    const html = renderToStaticMarkup(
      <ProductImage src="/catalog/photos/res-005.webp" alt="Respirador PFF3" />,
    );
    expect(html).toContain('src="/catalog/photos/res-005.webp"');
    expect(html).toContain("object-cover");
    expect(html).toContain('alt="Respirador PFF3"');
    expect(html).toContain('loading="lazy"');
  });

  it("ilustracao (/catalog/illustrations) renderiza com object-contain", () => {
    const html = renderToStaticMarkup(
      <ProductImage src="/catalog/illustrations/esmerilhadeira.svg" alt="Esmerilhadeira" />,
    );
    expect(html).toContain('src="/catalog/illustrations/esmerilhadeira.svg"');
    expect(html).toContain("object-contain");
  });

  it("imagem da API (/static/...) recebe o prefixo da origem da API e contain", () => {
    process.env.NEXT_PUBLIC_API_URL = API;
    const html = renderToStaticMarkup(
      <ProductImage src="/static/catalog/protecao-cabeca.svg" alt="Capacete" />,
    );
    expect(html).toContain(`src="${API}/static/catalog/protecao-cabeca.svg"`);
    expect(html).toContain("object-contain");
  });

  it("fallback: src vazio renderiza o placeholder generico da API com contain", () => {
    process.env.NEXT_PUBLIC_API_URL = API;
    const html = renderToStaticMarkup(
      <ProductImage src="" alt="Produto sem imagem" />,
    );
    expect(html).toContain(`src="${API}/static/catalog/generic.svg"`);
    expect(html).toContain("object-contain");
  });

  it("dimensoes reservadas (1:1) evitam salto de layout", () => {
    const html = renderToStaticMarkup(
      <ProductImage src="/catalog/photos/luv-003.webp" alt="Luva" />,
    );
    expect(html).toContain('width="640"');
    expect(html).toContain('height="640"');
  });
});
