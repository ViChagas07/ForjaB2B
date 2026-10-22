# Auditoria de lacunas — estado observado antes da entrega de documentação

> **Nota de proveniência:** este arquivo estava **vazio (0 bytes)** no início da sessão de
> 2026-10-22. Não havia uma auditoria histórica independente preservada. A tabela abaixo foi
> reconstruída por inspeção do repositório **antes** das mudanças desta entrega, para servir
> de base à coluna “antes” do [`FINAL_REPORT.md`](FINAL_REPORT.md). Não é uma auditoria
> externa nem substitui a avaliação do responsável.

**Data da observação:** 2026-10-22, antes dos commits de documentação desta sessão.
**Base Git:** `7ee3265` (7 commits à frente de `origin/main`).

## Lacunas observadas

| Item | Estado antes | Evidência no repositório |
| :--- | :--- | :--- |
| README raiz | **AUSENTE** (stub) | `README.md` tinha 26 bytes e apenas `# ForjaB2B`; `README.pt-BR.md` era um texto antigo de fases iniciais |
| Resumo em inglês | **AUSENTE** | Nenhum README com resumo EN |
| Badges | **AUSENTE** | Nenhum badge no README |
| Diagramas de arquitetura/busca | **AUSENTE** | Nenhum Mermaid no README |
| Tabela de validação honesta | **AUSENTE** | O `docs/STATUS.md` era um log append-only com estados superados (por exemplo, busca “fora do escopo” no topo e busca implementada no fim) |
| ADRs | **PARCIAL** | Existiam 0001–0004; faltavam RLS, preços, i18n, atributos, outbox, rate limiting, idempotência, timeouts e observabilidade. O ADR-0004 dizia “híbrida” sem destacar que embeddings estão desligados |
| ADR de busca atualizado | **PARCIAL** | `docs/ADRs/0004-busca-hibrida.md` com status antigo e sem o estado multilíngue/fallback atual |
| `docs/NON_GOALS.md` | **AUSENTE** | Não existia |
| `CHANGELOG.md` | **AUSENTE** | Não existia |
| `docs/INDEX.md` | **AUSENTE** | Não existia |
| `docs/STATUS.md` atual | **PARCIAL** | Arquivo de 67 KB, cronológico, com contradições entre fases; não era um retrato único |
| `docs/API.md` / snapshot OpenAPI | **AUSENTE** | OpenAPI só em runtime; nenhum mapa de endpoints versionado |
| Verificação de links internos | **AUSENTE** | Nenhum script/ferramenta no repositório |
| `docs/DEPLOY_RENDER.md` | **AUSENTE** | Nenhum `render.yaml`, blueprint, URL ou doc de deploy no Render |
| `docs/testing/LOAD.md` | **AUSENTE** | Nenhum k6/Locust/resultado de carga |
| Capturas de tela | **EXISTE** | 16 JPGs em `docs/validation/v3/` (pt-BR, en, ar, zh-CN × catálogo, busca, detalhe, carrinho) |
| CI | **EXISTE** | 3 workflows: `ci-backend.yml`, `ci-frontend.yml`, `ci-architecture.yml`; status dos runs não verificado |
| `docs/SECURITY.md` | **EXISTE** | Documento curto de segurança, linkado a partir do README novo |
| `docs/LGPD.md` | **EXISTE** | Direitos, anonimização e limitações |
| Rate limiting | **AUSENTE** | Nenhum middleware/limitador; Redis usado para refresh/cache/OAuth/readiness. O `PROGRESS` afirmava “rate limiting herdado do middleware global”, o que não corresponde ao código |
| Idempotência | **PARCIAL** | `idempotency_key` no **corpo** de pedido/pagamento/crédito e índices únicos; **não** há header `Idempotency-Key` nem middleware genérico |
| Observabilidade | **PARCIAL** | OTel, `/metrics`, logs JSON e health existem; Compose sobe OTel/Prometheus/Grafana, mas **não** há perfil opt-in e o Grafana local reinicia (datasource default duplicado) |
| Worker/beat | **PARCIAL** | Worker healthy; `celery-beat` reinicia por permissão em `celerybeat-schedule` |
| Mypy no repositório | **FALHA** | `mypy app --strict` limpo (285 arquivos), mas `mypy .` falha com 48 erros em 5 arquivos de teste; o CI executa `mypy .` |
| CORS | **AUSENTE** | Nenhum `CORSMiddleware`/`Access-Control-Allow-Origin`; frontend chama a API diretamente |
| Licença | **AUSENTE** | Nenhum `LICENSE` |
| Segredos no índice | **OK** | `.env` ignorado; `.env.example` com valores fictícios; nenhum segredo real encontrado na varredura |
| `.pyc` / artefatos | **OK** | `git ls-files` sem `.pyc`; `.gitignore` cobre `__pycache__` |
| Backups `.dump` | **NÃO IGNORADOS** | `backup_pre_migrations.dump` e `backup_v2_pre_migration.dump` estavam untracked e fora do `.gitignore` |
| Arquivos de agente | **VERSIONADOS** | `.commandcode/settings.json` e `.commandcode/taste/**` estão no Git; não foram alterados |
| Documentos duplicados/antigos | **EXISTE** | `README.pt-BR.md`, `temp_phase9bc.md`, `temp_v3_status.md`, log antigo do STATUS |
| Scripts ad-hoc na raiz | **EXISTE** | `check_products.py`, `create_attribute_table.sql`, `generate_seed_sql.py`; mantidos (sem referências quebradas) |

## O que esta auditoria não cobre

- Qualidade de tradução por falante nativo.
- Deploy real, carga real, comportamento em múltiplas réplicas.
- Status dos runs de CI no GitHub (não consultado).
- Licença e decisões comerciais.
- Segurança ofensiva (pentest) e conformidade formal.
