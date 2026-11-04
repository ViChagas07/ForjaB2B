import type { AbstractIntlMessages } from "next-intl";

import type { Locale } from "@/i18n/locales";

/**
 * Mensagens MÍNIMAS dos cartões do chat por idioma de resposta.
 *
 * O widget continua usando o locale do site para menus/placeholder. Apenas os
 * rótulos do cartão (SKU, preço sob consulta, CA e ações) usam o idioma da
 * mensagem, via um NextIntlClientProvider aninhado. Carregar o JSON completo do
 * locale aqui seria caro; este subconjunto é pequeno e determinístico.
 */
export const CHAT_CARD_MESSAGES: Record<Locale, AbstractIntlMessages> = {
  "pt-BR": {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Preço sob consulta, apenas para CNPJ",
      caValid: "CA válido",
    },
    aiChat: { viewProduct: "Ver produto", addToCart: "Adicionar ao carrinho" },
    currency: { chargeIn: "{value}" },
  },
  en: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Price on request, CNPJ only",
      caValid: "CA valid",
    },
    aiChat: { viewProduct: "View product", addToCart: "Add to cart" },
    currency: { chargeIn: "{value}" },
  },
  "zh-CN": {
    catalog: {
      sku: "SKU",
      priceOnRequest: "价格面议，仅限 CNPJ",
      caValid: "CA 有效",
    },
    aiChat: { viewProduct: "查看商品", addToCart: "加入购物车" },
    currency: { chargeIn: "{value}" },
  },
  ja: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "価格はお問い合わせください（CNPJ のみ）",
      caValid: "CA 有効",
    },
    aiChat: { viewProduct: "商品を見る", addToCart: "カートに追加" },
    currency: { chargeIn: "{value}" },
  },
  ko: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "가격 문의, CNPJ 전용",
      caValid: "CA 유효",
    },
    aiChat: { viewProduct: "상품 보기", addToCart: "장바구니에 추가" },
    currency: { chargeIn: "{value}" },
  },
  ru: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Цена по запросу, только для CNPJ",
      caValid: "CA действителен",
    },
    aiChat: { viewProduct: "Открыть товар", addToCart: "В корзину" },
    currency: { chargeIn: "{value}" },
  },
  es: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Precio bajo consulta, solo CNPJ",
      caValid: "CA válido",
    },
    aiChat: { viewProduct: "Ver producto", addToCart: "Añadir al carrito" },
    currency: { chargeIn: "{value}" },
  },
  de: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Preis auf Anfrage, nur mit CNPJ",
      caValid: "CA gültig",
    },
    aiChat: { viewProduct: "Produkt ansehen", addToCart: "In den Warenkorb" },
    currency: { chargeIn: "{value}" },
  },
  fr: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Prix sur demande, CNPJ uniquement",
      caValid: "CA valide",
    },
    aiChat: { viewProduct: "Voir le produit", addToCart: "Ajouter au panier" },
    currency: { chargeIn: "{value}" },
  },
  it: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "Prezzo su richiesta, solo CNPJ",
      caValid: "CA valido",
    },
    aiChat: { viewProduct: "Vedi prodotto", addToCart: "Aggiungi al carrello" },
    currency: { chargeIn: "{value}" },
  },
  ar: {
    catalog: {
      sku: "SKU",
      priceOnRequest: "السعر عند الطلب، CNPJ فقط",
      caValid: "CA صالح",
    },
    aiChat: { viewProduct: "عرض المنتج", addToCart: "أضف إلى السلة" },
    currency: { chargeIn: "{value}" },
  },
};
