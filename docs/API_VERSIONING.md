# Politica de versionamento e depreciacao da API

Versao atual: **`/api/v1`** (contrato em [`docs/api/openapi.json`](api/openapi.json),
documentacao em [`docs/api/index.html`](api/index.html)).

## 1. O que e uma mudanca compativel

Uma mudanca e **compativel** (pode entrar em `/api/v1`) quando um cliente
existente continua funcionando sem alteracao:

- adicionar endpoint novo;
- adicionar campo **opcional** em request (com default) ou em response;
- adicionar header novo opcional;
- adicionar valor novo em enum **somente** se os clientes ja tratarem valores
  desconhecidos (documentado como forward-compatible); caso contrario, tratar
  como incompativel;
- relaxar validacao (ex.: aumentar `max_length`), desde que o contrato aceite o
  valor antigo;
- adicionar resposta de erro documentada (status novo so para condicoes novas);
- mudar descricao/exemplo/documentacao sem mudar schema.

## 2. O que e uma mudanca incompativel

Exige **nova major** (`/v2`) e janela de depreciacao:

- remover ou renomear rota, campo, header ou parametro;
- tornar campo opcional em obrigatorio (request) ou obrigatorio em opcional
  (response) sem default;
- mudar tipo (`string` -> `number`, `int` -> `string`), formato ou unidade;
- mudar semantica de um campo/status existente;
- remover valor de enum ou alterar o significado de um valor;
- mudar codigo de status HTTP de sucesso/erro existente;
- mudar o esquema de autenticacao de uma rota;
- introduzir obrigatoriedade de idempotencia em rota que nao tinha (ver nota).

O CI roda `oasdiff breaking` contra o snapshot da `main`. Remocao de rota/campo,
mudanca de tipo ou de obrigatoriedade **quebram o job**; mudancas compativeis
passam. O snapshot e atualizado no mesmo PR (`python scripts/export_openapi.py`).

### Excecao documentada: `Idempotency-Key`

A partir desta versao, `POST /api/v1/orders` e `POST /api/v1/payments` exigem o
header `Idempotency-Key`. Para nao quebrar integracoes antigas, o campo
`idempotency_key` no corpo continua aceito como fallback durante a janela de
depreciacao. Novos clientes devem usar apenas o header. O OpenAPI marca o
header como opcional (para o fallback) e a descricao indica que ele e
obrigatorio para novas integracoes.

## 3. Quando abrir `/v2`

Abra `/v2` quando pelo menos uma mudanca incompativel for necessaria e nao
houver caminho aditivo razoavel. O processo:

1. Congele o contrato `/v1` (somente correcoes de seguranca e bugs).
2. Implemente `/v2` em paralelo, preferencialmente compartilhando casos de uso;
   a camada HTTP muda, o dominio nao.
3. Publique o OpenAPI `/v2` em `docs/api/openapi-v2.json` e a documentacao
   estatica correspondente.
4. Rode os dois caminhos em paralelo durante a janela de depreciacao.
5. Comunique, meça o trafego de `/v1` e so desligue apos o `Sunset`.

## 4. Janela de depreciacao

Padrao: **6 meses** entre o anúncio e o `Sunset` (ajustavel pelo responsavel
para 3–12 meses conforme criticidade e numero de integracoes).

| Fase | Prazo | O que acontece |
| :--- | :--- | :--- |
| Anuncio | D-0 | `Deprecation`, `Sunset` e `Link` na resposta; `deprecated: true` no OpenAPI; changelog e e-mail aos integradores |
| Acompanhamento | mensal | metrica `forja_deprecated_route_requests_total`; contato com consumidores ativos |
| Aviso final | D-30 | novo e-mail/changelog; dashboard com trafego restante |
| Desligamento | D-0 do Sunset | rota retorna 410/404; remover do OpenAPI na proxima major |

Rotas marcadas hoje:

| Rota | Substituida por | Sunset |
| :--- | :--- | :--- |
| `POST /api/v1/payments/webhook` (HMAC legado) | `POST /api/v1/payments/stripe/webhook` | 2027-04-30 |

### Cabecalhos

Toda resposta de rota marcada inclui:

```http
Deprecation: true
Sunset: Fri, 30 Apr 2027 00:00:00 GMT
Link: </api/v1/payments/stripe/webhook>; rel="successor-version"
Warning: 299 - "Webhook HMAC legado; use o webhook assinado do Stripe."
```

O OpenAPI correspondente tem `deprecated: true`. A metrica
`forja_deprecated_route_requests_total{method,route}` conta o uso por rota.

### Como marcar uma rota

```python
from datetime import date
from app.interface.deprecation import deprecated_route

@router.post("/rota-antiga", deprecated=True)
@deprecated_route(
    sunset=date(2027, 4, 30),
    successor="/api/v2/rota-nova",
    reason="Motivo curto e acionavel.",
)
async def rota_antiga(...): ...
```

## 5. Mapa de comunicacao

| Canal | Publico | Conteudo |
| :--- | :--- | :--- |
| `docs/API_VERSIONING.md` + `docs/api/` | integradores | contrato, prazos, substituicoes |
| changelog do repositorio | interno e integradores | mudancas compativeis e deprecacoes |
| e-mail para contatos tecnicos | clientes com integracao | anuncio, D-30 e desligamento |
| dashboard (Grafana) | interno | `forja_deprecated_route_requests_total` por rota |
| `README.md` secao API | novos desenvolvedores | versao atual e links |

## 6. Erros e idempotencia

- Erros usam Problem Details (RFC 9457) em `application/problem+json`, com
  `type`, `title`, `status`, `detail`, `instance`, `request_id` e, em validacao,
  `errors[]` por campo.
- `Idempotency-Key` e obrigatorio em criacao de pedido e checkout/pagamento;
  opcional em criacao/publicacao de produto e exclusao de dados (LGPD).
- Repeticao com mesmo payload devolve a resposta original e
  `Idempotent-Replayed: true`; payload diferente responde 422; requisicao em
  andamento responde 409 com `Retry-After`.
- Detalhes operacionais em [`docs/WEBHOOKS.md`](WEBHOOKS.md) e
  [`docs/MIGRATIONS.md`](MIGRATIONS.md).
