# Relatório final de prontidão — Forja B2B

**Data:** 2026-10-22
**Base Git:** `7ee3265` (branch `main`, 7 commits à frente de `origin/main`) + commits locais
de documentação desta entrega. **Nenhum push foi feito.**
**Escopo desta entrega:** documentação, ADRs, não-objetivos, higiene e relatório. Não houve
alteração de código funcional; as únicas mudanças de configuração foram o `.env.example`
(versão do índice) e `.gitignore` (backups).

> **Pré-requisitos (prompts 01–08):** não há registro de conclusão de todos eles no
> `PROGRESS.md`. O que existe: CI (3 workflows) e `docs/SECURITY.md`. O que não foi
> encontrado: `docs/DEPLOY_RENDER.md`, `docs/testing/LOAD.md`, rate limiting implementado e
> um relatório de deploy/carga. O `docs/readiness/GAP_AUDIT.md` estava **vazio (0 bytes)**.
> Esta entrega criou os documentos que faltavam com status explícito de **não executado**,
> em vez de inventar resultados.

## 1. Auditoria inicial → estado agora

A coluna “antes” vem do [`GAP_AUDIT.md`](GAP_AUDIT.md), reconstruído por inspeção do
repositório no início desta sessão. “Prova” aponta para o arquivo/comando que sustenta o
estado atual.

| Item | Antes | Agora | Prova |
| :--- | :--- | :--- | :--- |
| README raiz | **AUSENTE** (stub de 26 bytes) | **EXISTE** | `README.md` com resumo EN, 2 diagramas Mermaid, tabela de validação, execução local, limitações e licença |
| Resumo em inglês | **AUSENTE** | **EXISTE** | Bloco “English summary” no topo do `README.md` |
| Badges | **AUSENTE** | **EXISTE** | 3 badges de CI + 4 de stack no `README.md` |
| Diagramas de arquitetura e busca | **AUSENTE** | **EXISTE** | Dois blocos Mermaid no `README.md` |
| Tabela de validação honesta | **AUSENTE** | **EXISTE** | Seção “Estado de validação” do `README.md` e `docs/STATUS.md` |
| ADRs | **PARCIAL** (4) | **EXISTE** (4 + 9 novos) | `docs/ADRs/0004`–`0013`; índice em `docs/INDEX.md` |
| ADR de busca atualizado | **PARCIAL** | **EXISTE** | `docs/ADRs/0004-busca-hibrida.md` com estado real (`EMBEDDINGS_ENABLED=false`, fallback, multilíngue) |
| `docs/NON_GOALS.md` | **AUSENTE** | **EXISTE** | Tabela com 18 itens, incluindo os 15 pedidos e 3 lacunas explícitas |
| `CHANGELOG.md` | **AUSENTE** | **EXISTE** | Marcos de 2026-10-08 a 2026-10-22, datas do Git |
| `docs/INDEX.md` | **AUSENTE** | **EXISTE** | Mapa por tema |
| `docs/STATUS.md` atual | **PARCIAL** (log contraditório) | **EXISTE** | `docs/STATUS.md` conciso; log antigo em `docs/history/STATUS-log-2026-10.md` |
| `docs/API.md` | **AUSENTE** | **EXISTE** | Mapa de endpoints + OpenAPI em runtime |
| Verificação de links internos | **AUSENTE** | **EXISTE** | `scripts/check_markdown_links.py`; 41 arquivos, 0 links quebrados (46 com `--include-history`) |
| `docs/DEPLOY_RENDER.md` | **AUSENTE** | **EXISTE** (documento) | Deploy continua **NÃO EXECUTADO**; o doc diz isso no topo |
| `docs/testing/LOAD.md` | **AUSENTE** | **EXISTE** (documento) | Carga continua **NÃO EXECUTADA**; o doc diz isso no topo |
| Capturas de tela | **EXISTE** (16) | **EXISTE** | `docs/validation/v3/*.jpg`; 4 embutidas no README |
| CI | **EXISTE** | **EXISTE** | `.github/workflows/ci-{backend,frontend,architecture}.yml`; status não verificado |
| `docs/SECURITY.md` | **EXISTE** | **EXISTE** e linkado | `README.md` → `docs/SECURITY.md` |
| `docs/LGPD.md` | **EXISTE** | **EXISTE** e linkado | `README.md` → `docs/LGPD.md` |
| Rate limiting | **AUSENTE** | **AUSENTE** (documentado) | ADR-0010 proposto; não há middleware/limitador no código |
| Idempotência | **PARCIAL** (corpo) | **PARCIAL** (corpo) | ADR-0011; `idempotency_key` no JSON, não no header |
| Observabilidade | **PARCIAL** | **PARCIAL** | OTel/Prometheus/logs; sem perfil opt-in; Grafana local reinicia |
| Worker/beat | **PARCIAL** | **PARCIAL** | `forja-celery-beat` reinicia por permissão em `celerybeat-schedule` |
| Mypy no repositório | **FALHA** | **FALHA** (documentada) | `mypy .` → 48 erros em 5 arquivos de teste; `mypy app --strict` → 0 |
| CORS | **AUSENTE** | **AUSENTE** (documentado) | Sem `CORSMiddleware`; limitação no README |
| Licença | **AUSENTE** | **AUSENTE** (`[A DEFINIR]`) | Sem `LICENSE`; README explica direitos reservados |
| Backups `.dump` | **NÃO IGNORADOS** | **IGNORADOS** | `.gitignore` com `*.dump`; arquivos continuam untracked e não foram commitados |
| `.commandcode/` | **VERSIONADO** | **VERSIONADO** (informado) | 5 arquivos no Git; não alterados, conforme RULES |
| Documentos duplicados/antigos | **EXISTE** | **MOVIDOS** | `docs/history/` com README antigo, snapshots e log do STATUS, cada um com nota |
| Scripts ad-hoc na raiz | **EXISTE** | **EXISTE** (mantidos) | `check_products.py`, `create_attribute_table.sql`, `generate_seed_sql.py`; sem referências quebradas |

## 2. O que foi implementado nesta entrega

### Documentação

- `README.md` reescrito em pt-BR com resumo em inglês, arquitetura, fluxo de busca, decisões,
  validação, execução local, qualidade, segurança, observabilidade, API, deploy, limitações,
  capturas e licença.
- `docs/STATUS.md` reescrito como retrato único; o log antigo foi preservado em
  `docs/history/STATUS-log-2026-10.md`.
- `docs/INDEX.md`, `docs/API.md`, `docs/NON_GOALS.md`, `CHANGELOG.md`.
- `docs/readiness/GAP_AUDIT.md` (reconstruído, com nota de proveniência) e este relatório.
- `docs/DEPLOY_RENDER.md` e `docs/testing/LOAD.md` como **documentos de lacuna**, sem
  resultados inventados.

### ADRs

- 0005 PostgreSQL como fonte de verdade e RLS.
- 0006 preços fora do índice e preço consultivo.
- 0007 traduções armazenadas, 11 UI / 4 conteúdo e fallback.
- 0008 atributos JSONB com definições por categoria.
- 0009 outbox, reconciliação e índice versionado com alias.
- 0010 rate limiting com Redis e fail-open — **proposto, não implementado**.
- 0011 idempotência — **chave no corpo, não no header**.
- 0012 timeouts curtos e circuit breaker.
- 0013 observabilidade proporcional e segredos — **parcial**.
- 0004 atualizado com o estado real.

### Higiene

- Históricos movidos para `docs/history/` com banner de congelamento.
- `README.pt-BR.md` antigo, snapshots `temp_*` e log do STATUS preservados, não apagados.
- `$null` (arquivo vazio acidental) removido do Git.
- `.gitignore` com `*.dump`; `.env.example` com índice v2.
- Verificador de links internos; exclusão explícita de `docs/history/` e do log
  `docs/agent/PROGRESS.md` (documentos congelados).
- Notas de estado em `docs/ARCHITECTURE.md`, `docs/search/RUNBOOK.md`, `docs/RUNBOOK.md`,
  `docs/CATALOG_ADMIN.md` e `docs/search/PLAN.md`.

## 3. O que foi substituído por solução proporcional

| Necessidade “de produção” | Solução proporcional adotada | Limite |
| :--- | :--- | :--- |
| WAF/rate limiting | Validação de entrada, limites de tamanho, RLS, HMAC | Não há proteção contra abuso; ADR-0010 é proposta |
| Vault/Secrets Manager | `.env` ignorado, `.env.example` fictício, roles de banco separadas | Sem rotação/auditoria de segredo; Render não deployado |
| Pact | Testes de cliente HTTP no frontend + testes de API no backend | Sem contrato consumer-driven formal |
| Chaos engineering | Simulações pontuais (ES parado, breaker, reindex com falha) | Sem SLOs, automação ou blast radius |
| Réplicas de leitura/CDN | Uma instância PostgreSQL e assets versionados | Sem escala horizontal validada |
| ILM/snapshots ES | Índice versionado + alias + reindex/reconcile | Sem retenção/rollover automáticos |
| Pagamento real | `FakePaymentGateway` + máquina de estados + HMAC | Sem adquirente, conciliação ou PCI |
| Tradução em tempo real | Traduções armazenadas + `source_hash` + revisão manual | Sem TMS; árabe não revisado por nativo |
| Admin multilíngue | Admin em pt-BR; site do cliente em 11 idiomas | Decisão de escopo |
| Deploy Render | `docker-compose.prod.yml` para ES em VPS + runbook | Sem deploy executado |
| Teste de carga | Medições pontuais documentadas (não carga) | Sem resultados de throughput/latência sob carga |

## 4. Contagens finais e resultados

### Testes e qualidade (2026-10-22)

| Verificação | Resultado |
| :--- | :--- |
| Backend unidade + arquitetura | **425 passed** |
| Backend completo sem Docker | **427 passed, 251 skipped** |
| Backend completo com Docker/Testcontainers | **677 passed, 1 skipped** |
| Ruff check | **All checks passed** |
| Ruff format | **384 files already formatted** |
| Mypy `app --strict` | **285 files, 0 errors** |
| Mypy `.` (CI) | **48 errors em 5 arquivos de teste** |
| Import-linter | **4 contratos mantidos, 0 quebrados** |
| Frontend typecheck | **OK** |
| Frontend lint | **OK** (3 warnings `<img>`) |
| Frontend testes | **102 passed** (21 arquivos) |
| Frontend build | **OK** |
| Compose config | **OK** |
| Compose runtime | 9 healthy; `forja-grafana` e `forja-celery-beat` em restart; frontend criado, não iniciado |

### Higiene do índice

- `git ls-files` não contém `.env`, `.pyc`, `.dump`, `assets-src/` nem originais de fotos.
- `gitleaks` **não está instalado** nesta máquina; a varredura foi feita com regex de
  padrões comuns (AWS key, chave privada PEM, token GitHub, chave OpenAI) e não encontrou
  achados. Isso **não** substitui um secret scanner dedicado no CI.
- Os dois backups `.dump` continuam no disco, mas estão ignorados por `.gitignore` e não
  foram commitados.
- `.commandcode/` tem 5 arquivos versionados; não foram alterados (ver pendência 11).

### Carga

**Não executada.** Não há k6/Locust, script de carga ou resultado versionado. O
[`docs/testing/LOAD.md`](../testing/LOAD.md) registra o roteiro e o aviso de que números locais
não representam o Render.

### Simulações de falha

- Evidência V2 (sessão anterior, não reexecutada em 2026-10-22): Elasticsearch parado →
  `search_mode=postgres_fallback`; primeira chamada ~2,05 s; com breaker aberto 8–15 ms;
  recuperação após `start` + `reconcile`; edição de catálogo durante a queda. Ver
  [`docs/agent/PROGRESS.md`](../agent/PROGRESS.md) e
  [`docs/search/RUNBOOK.md`](../search/RUNBOOK.md).
- Reindex com documento rejeitado → alias **não** trocado e exit code ≠ 0 (Fase 8A); ver
  [`docs/search/RUNBOOK.md`](../search/RUNBOOK.md).
- **Não** houve chaos engineering completo, teste de múltiplas réplicas ou falha de
  PostgreSQL/Redis em produção.

### Falhas de infraestrutura local observadas

- `forja-grafana`: `datasource.yaml` com mais de um datasource default → provisioning falha
  e o container reinicia.
- `forja-celery-beat`: `Permission denied: 'celerybeat-schedule'` → beat reinicia; a
  reconciliação automática da busca fica parada.
- Nenhum desses é corrigido nesta entrega (fora do escopo de documentação), mas ambos
  estão registrados no README/STATUS.

## 5. Não-objetivos

Os 15 itens pedidos estão em [`docs/NON_GOALS.md`](../NON_GOALS.md), com justificativa, o
que foi feito no lugar e o que seria feito em produção. Além deles, o documento marca
como **lacuna** (não escolha): rate limiting, teste de carga e deploy em provedor.

## 6. O que o responsável ainda precisa fazer

1. **Push e CI:** revisar os commits locais, fazer push e verificar os 3 workflows. O
   `mypy .` local falha em 48 erros de teste; o job backend deve ficar vermelho até a
   correção (ou até o CI ser ajustado com justificativa).
2. **Proteção de branch:** exigir PR, revisão e status checks verdes em `main`.
3. **CORS/proxy:** habilitar CORS no backend ou colocar frontend/API no mesmo domínio;
   sem isso o frontend não funciona em navegador comum.
4. **Infra local:** corrigir o datasource default duplicado do Grafana e a permissão do
   `celerybeat-schedule`; reexecutar `reconcile`.
5. **Rate limiting:** implementar ADR-0010 ou declarar que o WAF/edge cobre; hoje não há
   proteção de aplicação.
6. **Deploy:** criar `render.yaml`/serviços, configurar Environment Groups, migrations,
   seed (só se demo), índice e healthchecks; seguir `docs/DEPLOY_RENDER.md`. Não há URL
   pública hoje.
7. **Licença:** escolher e adicionar `LICENSE`; sem isso, todos os direitos reservados.
8. **Traduções:** revisão por falante nativo (árabe, especialmente), termos de EPI e
   consistência de gênero/tom.
9. **Capturas:** as 16 existentes cobrem i18n; se quiser capturas de admin/checkout,
   gerar novas e salvar em `docs/images/` (não inventar mockups).
10. **GitHub Pages:** não há workflow de Pages; se a intenção é publicar a documentação,
    criar o workflow e ativar Pages nas configurações do repositório.
11. **Decisão sobre `.commandcode/`:** 5 arquivos de ferramentas do agente estão
    versionados; decidir se devem sair do repositório (não foram alterados).
12. **Scripts ad-hoc na raiz:** `check_products.py`, `create_attribute_table.sql` e
    `generate_seed_sql.py` continuam na raiz; mover ou remover se não forem úteis.
13. **Dados legados:** três produtos do seed têm descrição nula; decidir se corrigir o seed
    ou aplicar `NOT NULL` após o preenchimento.
14. **Embeddings:** se quiser o modo `hybrid` como padrão, validar modelo, memória, custo e
    qualidade em staging; hoje está desligado.

## 7. Riscos remanescentes

- **CI vermelha por mypy** e possível falha de outros jobs não verificados.
- **Frontend inutilizável em navegador comum** por CORS ausente (a validação visual usou
  Chromium sem checagem de CORS).
- **Reconciliação da busca parada** enquanto o beat reinicia; índice pode ficar defasado.
- **Sem rate limiting/WAF**, exposição a abuso e brute force.
- **Sem deploy real**, o comportamento em Render (pool, disco efêmero, pgvector, egress) é
  desconhecido.
- **Sem teste de carga**, não há base para SLO/capacity planning.
- **Traduções não revisadas**, com risco de terminologia inadequada.
- **Licença indefinida**, uso comercial/ redistribuição não autorizados por padrão.
- **Embeddings desligados**, a busca não cobre consultas por intenção sem palavras exatas.
- **Pagamento fake**, não há validação de adquirente, conciliação ou PCI.

## 8. Resumo em 10 linhas (descrição do repositório / LinkedIn)

1. Forja B2B é uma plataforma de e-commerce B2B para EPIs e máquinas industriais, em um
   projeto de portfólio com dados fictícios.
2. Backend em FastAPI/Python 3.12 com Clean Architecture, PostgreSQL 16, RLS multi-tenant
   e preços resolvidos por empresa.
3. Frontend em Next.js 14 com 11 idiomas de interface, RTL para árabe e 4 idiomas de
   conteúdo.
4. Catálogo, carrinho, pedido, crédito, faturamento, pagamento simulado, LGPD e
   administração de catálogo com atributos por categoria.
5. Busca lexical no Elasticsearch 9.5 com fallback PostgreSQL; semântica com pgvector/RRF
   implementada, mas desligada por padrão.
6. Preço nunca entra no índice: visitante vê “sob consulta” e cada empresa vê sua condição.
7. 425 testes de unidade/arquitetura e 677 testes com Docker (1 skipped), 102 testes de
   frontend e build aprovado na última execução local.
8. CI, OpenTelemetry/Prometheus e documentação de arquitetura/ADRs presentes; rate limiting,
   deploy e teste de carga ainda não implementados.
9. Limitações conhecidas: CORS ausente, `mypy .` com 48 erros em testes, Grafana/beat
   instáveis e traduções não revisadas por nativos.
10. Sem licença definida; o código está sob todos os direitos reservados por padrão.

## 9. Commits desta entrega

Commits locais, sem push (ver `git log` para os hashes finais):

- `docs: reescreve README e organiza documentação histórica`
- `docs: adiciona ADRs, não-objetivos, changelog e índice`
- `docs: adiciona relatório de prontidão e verificação de links`

A entrega não altera código funcional. As únicas mudanças fora de `docs/` são `README.md`,
`CHANGELOG.md`, `.env.example` (versão do índice), `.gitignore` (`*.dump`), remoção do
arquivo vazio `$null` e o script `scripts/check_markdown_links.py`.
