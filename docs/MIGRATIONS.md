# Migrations, rollback e drill

> Atualizado em 2026-10-22. Fonte de verdade do schema: `backend/alembic/versions`.
> O banco operacional e o PostgreSQL; Elasticsearch/pgvector sao derivados.

## 1. Regras

- Toda migration tem `upgrade()` e `downgrade()` executavel.
- O `downgrade()` nunca e um `pass`, nunca levanta `NotImplementedError` e nao
  depende de estado que ele mesmo removeu.
- Quando a reversao perde um estado de negocio que o schema antigo nao
  representa, a perda e **explicita** e documentada nesta pagina (migration
  marcada como reversivel com perda). Nao ha migration marcada como
  `IRREVERSIVEL:` neste repositorio; se uma surgir, o cabecalho deve conter o
  marcador e esta pagina deve trazer o motivo e o procedimento alternativo.
- O teste de arquitetura `backend/tests/architecture/test_migrations.py`
  falha se alguma migration ficar sem downgrade funcional ou se uma migration
  irreversivel nao estiver documentada.
- Migrations rodam com `forja_admin` (`DATABASE_ADMIN_URL`). O runtime
  (`forja_app`) nunca executa DDL.

## 2. Inventario (revisao 0022)

| Revisao | Assunto | Downgrade | Observacao |
| :--- | :--- | :--- | :--- |
| 0001 | Empresas, usuarios, enderecos | Sim | Remove as tabelas na ordem inversa das FKs. |
| 0002 | Catalogo e faixas de preco | Sim | Remove produtos, marcas e categorias. |
| 0003 | Credito | Sim | Remove conta e lancamentos. |
| 0004 | Pedidos e faturamento | Sim | Remove faturas, itens e pedidos. |
| 0005 | Privacidade e auditoria | Sim | Remove consentimentos e auditoria. |
| 0006 | Busca de identidade no login | Sim | Remove policy e revoga SELECT da role de auth. |
| 0007 | Carrinho | Sim | Remove itens e carrinhos. |
| 0008 | Identidade externa (OAuth) | Sim | Remove a tabela de identidades externas. |
| 0009 | Pagamento | Sim | Remove eventos e pagamentos. |
| 0010 | Notificacoes | Sim | Remove policy de despacho, preferencias e outbox. |
| 0011 | Outbox de busca | Sim | Remove a tabela global `search_outbox`. |
| 0012 | Extensoes de fallback textual | Sim (parcial por desenho) | Remove apenas os indices; `unaccent`/`pg_trgm` pertencem ao bootstrap e podem ser compartilhadas. |
| 0013 | Embeddings (pgvector) | Sim (parcial por desenho) | Remove tabela/indice; a extensao `vector` pertence ao bootstrap. |
| 0014 | Preco por empresa | Sim | Remove `company_price_rules`. |
| 0015 | Imagem do produto | Sim | `drop_column` remove os valores de `image_url` (perda inerente ao rollback de coluna). |
| 0016 | Traducoes de produto | Sim | Remove traducoes armazenadas. |
| 0017 | Definicoes de atributos | Sim | Remove o registry persistido. |
| 0018 | Constraints do admin | Sim, com perda de estado | `DRAFT` e normalizado para `INACTIVE` antes de restaurar a constraint antiga. |
| 0019 | Locale do pedido | Sim | Remove `content_locale` de pedidos e itens. |
| 0020 | Status `PAID` | Sim, com perda de estado | `PAID` e normalizado para `RECEIVED` antes de restaurar a constraint antiga. |
| 0021 | Chaves de idempotencia (admin/API) | Sim | Remove `idempotency_keys` e suas policies RLS. |
| 0022 | Escopo multi-tenant das chaves de idempotencia | Sim | Recria os indices unicos de `orders`/`payments` com `company_id`; o downgrade volta ao indice global (pode falhar se houver chaves duplicadas entre empresas). |

Nao ha migration irreversivel. As perdas de 0015, 0018 e 0020 sao
intencionais e ocorrem apenas no rollback; o upgrade seguinte nao recria os
valores perdidos.

## 3. Drill de rollback

`scripts/migration_drill.py` prova o ciclo completo em um banco descartavel:

1. cria `forja_scratch_migration_*` (prefixo obrigatorio) no mesmo cluster;
2. replica o bootstrap real (`docker/postgres`: roles, extensoes, schema `app`,
   funcoes RLS);
3. `alembic upgrade head`;
4. aplica o seed e registra contagens/checksums de produtos, empresas,
   usuarios, regras de preco e traducoes;
5. `alembic downgrade base` (padrao) ou `alembic downgrade -N` com `--steps N`;
6. `alembic upgrade head` novamente;
7. reaplica o seed (idempotente) e compara contagens/checksums;
8. roda `alembic check` e confere a revisao atual;
9. remove o banco descartavel que criou (ou o preserva com `--keep`).

```bash
python scripts/migration_drill.py
python scripts/migration_drill.py --steps 3
python scripts/migration_drill.py --json
python scripts/migration_drill.py --keep   # inspecao manual; remover depois
```

O script nunca aponta para `POSTGRES_DB` e so remove nomes `forja_scratch_*`
criados pela propria execucao. Qualquer falha retorna codigo != 0.

### Ultimo resultado registrado

Execucao de 2026-10-22 (Docker de pe, PostgreSQL 16 + pgvector):

- banco descartavel, bootstrap, upgrade/seed/downgrade/upgrade/seed e
  `alembic check`: **OK**;
- seed antes e depois identico: 50 produtos, 4 empresas, 13 usuarios, 4 regras
  de preco e 150 traducoes (checksums identicos);
- revisao final `0022` (head), sem divergencia de esquema;
- o banco descartavel foi removido ao final.

Tempos registrados (execucao final de 2026-10-22, Docker de pe, cache aquecido):

| Etapa | Tempo |
| :--- | ---: |
| criar banco descartavel | 0,92 s |
| bootstrap (roles/extensoes/schema `app`) | 0,87 s |
| upgrade head inicial | 8,80 s |
| seed inicial | 5,86 s |
| snapshot do seed (antes) | 0,62 s |
| downgrade base | 6,18 s |
| upgrade head final | 8,48 s |
| seed final | 2,20 s |
| snapshot do seed (depois) | 0,31 s |
| `alembic check` | 2,92 s |
| **total** | **41,10 s** |

O tempo varia com o I/O do Docker Desktop: a primeira execucao a frio levou
~290 s e uma execucao intermediaria com cache quente levou 25,87 s. O relatorio
completo sai em JSON com `--json` e fica registrado no
`docs/STATUS.md`.

## 4. CI

O job `migrations` do Prompt 02 **ainda nao existe** no
`.github/workflows/ci-backend.yml`; por isso o drill ainda nao esta conectado
ao CI. Pendencia registrada: quando o job for criado, executar
`python scripts/migration_drill.py` em um service PostgreSQL descartavel
(imagem `pgvector/pgvector:0.8.7-pg16`) e tornar a etapa bloqueante.

Enquanto isso, o CI atual ja executa o teste de arquitetura das migrations na
suíte `pytest tests/`.

## 5. Procedimento manual de rollback

1. Faca backup logico antes de qualquer rollback (`scripts/backup_db.py`).
2. Confirme a revisao atual: `alembic current` (com `DATABASE_ADMIN_URL`).
3. Reverta uma revisao: `alembic downgrade -1` (ou `make migration-rollback`).
4. Reaplique: `alembic upgrade head` e `alembic check`.
5. Se o rollback for de 0018/0020, esteja ciente da normalizacao de estado
   descrita na tabela acima.

Nunca rode `downgrade base` no banco de desenvolvimento sem backup; o drill
usa apenas bancos descartaveis.
