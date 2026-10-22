# ADR-0008: Atributos de produto em JSONB com definições por categoria

- **Status:** aceito e implementado
- **Data:** 2026-10-12
- **Contexto do código:** `backend/app/domain/product_attributes.py`,
  `backend/app/application/product_attributes.py`,
  `backend/app/seed_data/attribute_definitions.json`,
  `backend/alembic/versions/0017_product_attribute_definitions.py`

## Contexto

EPIs e máquinas têm atributos diferentes por categoria: tamanho de luva, cor de capacete,
potência/tensão de ferramenta, CA de EPI, material, peso etc. Criar colunas para cada
atributo geraria uma tabela larga e migrations frequentes; um EAV clássico fragmenta a
leitura e dificulta a validação. O admin precisa renderizar formulários dinâmicos e a API
pública só deve devolver atributos preenchidos, com rótulo e unidade.

## Decisão

1. Os valores ficam em **`products.attributes` JSONB** (índice GIN).
2. As **definições** ficam em `product_attribute_definitions` e em um JSON versionado no
   repositório (`attribute_definitions.json`), carregado em um registry em memória.
3. Cada definição tem `key`, `label`, `type` (`text`, `number`, `enum`, `boolean`), `unit`,
   `options`, `scope` (`global` ou lista de categorias), `section`, `display_order`,
   `required`, `min/max` e `max_length`.
4. O validador de domínio **rejeita chave desconhecida, chave fora do escopo da categoria,
   tipo errado, enum inválido e valor fora do intervalo**; valores vazios (`null`, `""`,
   whitespace, lista vazia) são descartados.
5. Números são normalizados para `Decimal`; texto é `strip`; a API pública devolve apenas
   atributos com valor, como lista ordenada `{key, label, value, unit}`.
6. Rótulos e opções de enum têm dicionário por locale (`attribute_dictionary.json`); o
   `label` do registry é o fallback `pt-BR`.
7. O admin carrega as definições por categoria e renderiza os inputs conforme o tipo;
   trocar de categoria remove atributos que não se aplicam, com aviso.

## Alternativas consideradas

- **Colunas fixas:** migrations constantes e muitos campos nulos; rejeitado.
- **EAV (tabela `attribute_values`):** consultas e ordenação mais complexas, e o snapshot
  do pedido teria de juntar várias linhas; rejeitado para este escopo.
- **Documento NoSQL separado:** duplicaria a fonte de verdade e a transação com o produto.
- **JSONB sem definições:** flexível, mas sem validação, labels ou formulário dinâmico.

## Consequências

- Adicionar um atributo é uma mudança de dados (definição), não de schema.
- O banco não impõe FK para cada atributo; a validação é da aplicação, então o registry
  precisa estar sempre disponível e testado.
- O GIN index ajuda buscas por atributo, mas consultas analíticas complexas exigem
  `jsonb_path_ops`/índices específicos.
- A API pública precisa traduzir o label; hoje o dicionário cobre os locales de conteúdo,
  mas a revisão de tradução é manual.
- O seed tem 13 definições (7 globais + 6 por categoria).

## Em produção real, seria diferente

- Versionar as definições com vigência e migrar valores quando um tipo muda (texto →
  enum, por exemplo), com dry-run e relatório de incompatibilidades.
- Gerar JSON Schema a partir das definições para validar também na borda e no frontend.
- Criar índices GIN específicos por consulta analítica e materializar atributos usados em
  filtros de busca.
- Ter um catálogo de atributos com governança (quem pode criar/alterar), auditoria e
  revisão de traduções.
- Testar compatibilidade de dados antigos ao publicar uma nova versão do registry.
