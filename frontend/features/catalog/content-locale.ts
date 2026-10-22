/**
 * A nota de idioma do conteudo aparece apenas quando o content_locale entregue
 * pela API difere do idioma da interface. Carrinho e pedido nao exibem nada.
 */
export function showContentLocaleNote(
  uiLocale: string,
  contentLocale: string | null | undefined,
): boolean {
  return Boolean(contentLocale) && contentLocale !== uiLocale;
}
