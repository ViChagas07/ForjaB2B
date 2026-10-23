# Contrato OpenAPI (versionado)

`docs/api/openapi.json` e o **snapshot versionado** do contrato da API. Ele e
gerado pelo backend FastAPI (fonte de verdade) e nao deve ser editado a mao.

| Arquivo | Origem | Papel |
| :--- | :--- | :--- |
| `docs/api/openapi.json` | `python scripts/export_openapi.py` | contrato publicado e comparado no CI |
| `docs/api/index.html` | Redoc CLI | documentacao estatica navegavel |
| `frontend/core/domain/api-schema.d.ts` | `openapi-typescript` | tipos TypeScript do contrato |

## Regenerar

```bash
cd backend
python scripts/export_openapi.py          # grava ../docs/api/openapi.json
python scripts/export_openapi.py --check  # falha se o snapshot divergir
```

O export usa chaves ordenadas, indentacao fixa e UTF-8 sem BOM. Duas execucoes
produzem exatamente os mesmos bytes; nenhum dado de ambiente entra no arquivo.

## Documentacao estatica (Redoc)

```bash
# opcao A: npx (Node 20+)
npx --yes @redocly/cli@latest build-docs docs/api/openapi.json -o docs/api/index.html

# opcao B: Docker
docker run --rm -v "$PWD:/work" redocly/cli build-docs /work/docs/api/openapi.json \
  -o /work/docs/api/index.html
```

Abra `docs/api/index.html` no navegador. As tags, exemplos e respostas de erro
vem do proprio contrato.

## Swagger local

Com o Compose de pe:

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Redoc (runtime): desabilitado de proposito (`redoc_url=None`); use o HTML
  estatico acima.

Em `ENVIRONMENT=production`, `/docs` e `/openapi.json` ficam desligados; o
contrato publicado e o snapshot versionado.

## GitHub Pages (passo manual do responsavel)

O repositorio nao publica Pages automaticamente (evita acoplar deploy a um
workflow sem revisao). Para publicar:

1. Gere `docs/api/index.html` novamente quando o contrato mudar.
2. Em **Settings > Pages**, escolha **Deploy from a branch**.
3. Selecione a branch `main` e a pasta `/docs` (a URL fica
   `https://<usuario>.github.io/<repo>/api/`).
4. Confirme que `docs/api/index.html` referencia apenas assets relativos/HTTPS
   (o Redoc CLI gera um arquivo autocontido).
5. Opcional: aponte um dominio proprio em **Custom domain**.

Se preferir publicar apenas a API, crie um workflow com `actions/upload-pages-artifact`
apontando para `docs/api`. Isso exige permissao `pages: write` e um ambiente
protegido; a decisao e do responsavel.

## CI: contrato e drift

O job `openapi-contract` (`.github/workflows/ci-backend.yml`) executa:

1. `python scripts/export_openapi.py` e `git diff --exit-code -- docs/api/openapi.json`
   — qualquer mudanca de contrato exige atualizar o snapshot no mesmo PR;
2. `oasdiff breaking` contra o snapshot da `main` — remocao de rota/campo,
   mudanca de tipo ou de obrigatoriedade falham; mudancas compativeis passam;
3. `openapi-typescript` + `git diff --exit-code frontend/core/domain/api-schema.d.ts`
   — o tipo do frontend nao pode divergir do contrato.

Para reproduzir localmente a checagem de compatibilidade:

```bash
git show origin/main:docs/api/openapi.json > /tmp/base-openapi.json
docker run --rm -v "$PWD:/work" tufin/oasdiff breaking \
  --fail-on ERR \
  /work/tmp-base-openapi.json /work/docs/api/openapi.json
```

## Tipos TypeScript (migracao gradual)

`frontend/core/domain/api-schema.d.ts` e gerado e versionado. Os contratos
manuais mais criticos (`Order`, `Payment`, `AdminProductDetail`) continuam sendo
a fonte usada pela UI, mas `frontend/core/domain/openapi-types.ts` falha o
`tsc` se o OpenAPI remover/renomear um campo que eles consomem. Contratos novos
devem importar `ApiSchemas`/`ApiOperations` diretamente; a substituicao dos
tipos manuais e incremental, sem reescrita em massa.

## Compatibilidade

A politica completa (o que quebra, janela de depreciacao e `/v2`) esta em
[`docs/API_VERSIONING.md`](../API_VERSIONING.md). Resumo: campos novos sao
opcionais, remocoes/mudancas de tipo exigem nova major (`/v2`) e rotas
depreciadas emitem `Deprecation`, `Sunset` e `Link`.
