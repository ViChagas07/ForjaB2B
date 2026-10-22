# ADR-0007: Traduções armazenadas, 11 idiomas de interface e 4 de conteúdo

- **Status:** aceito e implementado (traduções de demonstração não revisadas por nativos)
- **Data:** 2026-10-13
- **Contexto do código:** `backend/app/domain/i18n.py`,
  `backend/app/application/i18n.py`, `backend/app/infrastructure/db/translations.py`,
  `backend/alembic/versions/0016_product_translations.py`,
  `frontend/i18n/locales.ts`, `frontend/messages/*.json`

## Contexto

O catálogo precisa ser exibido em vários idiomas sem transformar cada request em uma
chamada a um serviço de tradução. O conteúdo de produto (nome, descrição, atributos) é
editado em `pt-BR`; a interface tem um conjunto maior de idiomas. Traduções automáticas
podem ser úteis para demonstração, mas não são confiáveis para produção sem revisão.

## Decisão

1. **Duas listas explícitas:**
   - `UI_LOCALES` = 11 idiomas de interface: `pt-BR`, `en`, `zh-CN`, `ja`, `ko`, `ru`,
     `es`, `de`, `fr`, `it`, `ar`.
   - `CONTENT_LOCALES` = 4 idiomas de conteúdo: `pt-BR`, `en`, `es`, `ar`.
2. **`pt-BR` é a origem.** Traduções de conteúdo ficam em `product_translations`
   (`product_id`, `locale`, `name`, `description`, `attributes` JSONB, `source_hash`,
   `status`, `translated_at`).
3. **Fallback em duas etapas:** idioma pedido → `en` (se não for conteúdo) → `pt-BR`,
   **campo a campo**. Um produto pode ter nome em `en` e descrição em `pt-BR`.
4. **`source_hash`** (SHA-256 do nome + descrição + atributos de texto em `pt-BR`) detecta
   quando a origem mudou. A tradução antiga continua sendo servida com `status=stale` até
   ser atualizada; nada é apagado automaticamente.
5. **Nenhum provedor de tradução no request.** A porta `TranslationProvider` existe, mas o
   padrão é `NullTranslationProvider`; o admin edita a tradução manualmente e pode marcar
   `reviewed`.
6. A interface usa `next-intl` com 11 dicionários; o árabe é o único RTL da lista
   (`rtlLocales = ["ar"]`). A direção é derivada de `directionForLocale()`.
7. A busca multilíngue indexa campos `name_{locale}`, `description_{locale}` e
   `attributes_text_{locale}` para `en`, `es` e `ar`, além dos campos `pt-BR`.

## Alternativas consideradas

- **Traduzir em tempo de request (API paga):** latência, custo, dependência externa e risco
  de traduzir preço/SKU/marca. Rejeitado para o runtime.
- **Guardar apenas JSON por locale no frontend:** não cobre conteúdo de produto nem
  permite edição pelo admin.
- **Um único idioma de conteúdo:** mais simples, mas não demonstra o requisito
  internacional.
- **Tradução automática no seed e pronto:** aceito apenas como demonstração; o estado fica
  `machine` e o texto é revisável.

## Consequências

- 1.037 chaves de interface foram traduzidas e um teste de paridade impede chaves faltando
  ou valores iguais ao `pt-BR` (com allowlist).
- O árabe e os demais idiomas **não foram revisados por falantes nativos**; há erros
  possíveis de tom e terminologia.
- A busca de fallback PostgreSQL usa apenas `pt-BR`; idiomas de conteúdo não são
  consultados nesse caminho.
- Adicionar um quinto idioma de conteúdo exige traduções reais, analisador/stopwords no
  Elasticsearch e revisão do fallback — não é só configuração.
- O admin permanece em português por decisão de escopo.

## Em produção real, seria diferente

- Contratar revisão por falante nativo (especialmente árabe) e um fluxo de aprovação com
  histórico de versões.
- Integrar um TMS (Crowdin, Lokalise, Phrase) com webhooks e memória de tradução, mantendo
  o banco como cache de leitura.
- Usar `source_hash` + fila para marcar traduções obsoletas automaticamente quando o
  `pt-BR` mudar, com alerta de cobertura por locale.
- Definir política de idioma por mercado, moeda e formato de número/data; hoje a moeda é
  sempre BRL e os numerais são ocidentais.
- Adicionar testes de acessibilidade/RTL e pseudo-localização no CI.
