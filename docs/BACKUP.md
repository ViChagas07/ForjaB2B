# Backup, restauracao e recuperacao

> Atualizado em 2026-10-22. Scripts: `scripts/backup_db.py`,
> `scripts/restore_drill.py`. O PostgreSQL e a fonte de verdade; Elasticsearch e
> pgvector sao derivados e reconstruiveis.

## 1. Politica

| Item | Desenvolvimento | Producao sugerida |
| :--- | :--- | :--- |
| Frequencia | Antes de cada migration/rollback e sob demanda | Backup gerenciado diario + PITR (quando o provedor oferecer); `pg_dump` diario para retencao externa |
| Retencao local | 7 arquivos (`BACKUP_RETENTION=7`) | 7 a 30 dias em object storage, conforme custo/contrato |
| Formato | `pg_dump --format=custom --compress=6` | idem, ou export gerenciado do provedor |
| Local | `backups/` na raiz (fora do volume do banco; ignorado pelo Git) | bucket externo com versionamento e criptografia |
| RPO | Ultimo backup manual | PITR: minutos; dump diario: ate 24 h |
| RTO | Minutos (banco pequeno) | Minutos a horas, dependendo do tamanho e do provedor |
| Teste | `python scripts/restore_drill.py` | Drill trimestral em banco descartavel + restauracao gerenciada |

**Nunca** versione dumps: eles contem dados pessoais (e-mail, telefone, hash de
CPF, enderecos) e segredos de sessao. `.gitignore` cobre `*.dump` e
`backups/`.

## 2. Backup local

```bash
python scripts/backup_db.py                 # backups/forja_db_<UTC>.dump
python scripts/backup_db.py --keep 14       # retencao
python scripts/backup_db.py --json          # relatorio (tamanho, sha256, rotacao)
```

O script:

- roda `pg_dump` dentro do container `postgres` e grava fora do volume;
- usa o superusuario de bootstrap **apenas em desenvolvimento**: as tabelas de
  tenant usam `FORCE ROW LEVEL SECURITY` e a role `forja_admin` nao consegue
  exportar todas as linhas;
- valida tamanho > 0 e o magic header `PGDMP` antes de publicar o arquivo;
- grava em arquivo temporario e faz `os.replace` (nunca deixa dump parcial com o
  nome final);
- roda a rotacao apenas em arquivos `forja_db_<timestamp>.dump` (outros arquivos
  do diretorio sao preservados);
- nao coloca credenciais em argumentos: a autenticacao e local (socket do
  container) e nenhuma senha e impressa.

`make db-backup` e equivalente.

## 3. Restauracao comprovada (drill)

```bash
python scripts/restore_drill.py              # usa o backup mais recente
python scripts/restore_drill.py --backup backups/forja_db_20261022T225027Z.dump
python scripts/restore_drill.py --json
```

Fluxo:

1. valida o dump (tamanho + `PGDMP`);
2. registra contagens do banco operacional (somente leitura);
3. cria `forja_scratch_restore_*` no mesmo cluster;
4. restaura com `pg_restore --no-owner --no-acl --exit-on-error`;
5. aplica `alembic upgrade head` no banco restaurado, roda `alembic current` e
   `alembic check`;
6. confere contagens de produtos, empresas, usuarios, regras de preco e
   traducoes, e a presenca de `vector`, `unaccent`, `pg_trgm`, `pgcrypto` e
   `uuid-ossp`;
7. confirma que o banco operacional tem as mesmas contagens de antes;
8. remove **apenas** o banco `forja_scratch_*` que criou.

O dump pode ter sido tirado antes da ultima migration; por isso o drill aplica
`upgrade head` antes do `check`. Se uma migration futura for irreversivel, o
backup continua sendo o caminho de recuperacao (o rollback nao e).

### Ultimo resultado registrado

Execucao final de 2026-10-22 (Docker de pe, schema 0022):

- arquivo: `forja_db_20261022T235915Z.dump`, **226.309 bytes**
  (sha256 `b3da36ca...d5db9ce1`);
- `pg_restore`: 1,45 s (execucao final; 9,81 s na primeira);
- `alembic upgrade/current/check`: 9,49 s;
- total do drill: 13,27 s;
- contagens restauradas: 50 produtos, 4 empresas, 13 usuarios, 4 regras de
  preco, 150 traducoes, 0 eventos de outbox;
- extensoes: `vector`, `unaccent`, `pg_trgm`, `pgcrypto`, `uuid-ossp`;
- banco operacional inalterado (contagens antes = depois);
- banco descartavel removido ao final.

## 4. Procedimento de restauracao em producao

1. **Pare escritas** (modo manutencao ou escala o backend para zero) para evitar
   que dados novos sejam perdidos durante a troca.
2. Gere um backup final do banco atual, mesmo que ele esteja degradado.
3. Restaure em uma **instancia nova** (nunca por cima da atual):
   - provedor gerenciado: use PITR/recuperacao para uma nova instancia;
   - VPS/Compose: crie um banco vazio e rode `pg_restore` com um usuario
     administrador; depois aplique `alembic upgrade head`.
4. Valide contagens, extensoes, `alembic current` e uma consulta de catalogo
   (produto publicado, preco por empresa, traducao).
5. Troque a connection string dos servicos (Environment Group no Render ou
   `.env` no host) e reinicie backend/worker.
6. Reindexe o Elasticsearch a partir do PostgreSQL
   (`python -m app.modules.search.interface.cli reindex`) e rode `reconcile`.
7. Mantenha a instancia antiga suspensa por alguns dias antes de removê-la.

## 5. Backups gerenciados do Render

Consulta a documentacao oficial em 2026-10-22:
<https://render.com/docs/postgresql-backups>.

- Bancos **pagos** tem backup continuo com **point-in-time recovery (PITR)**.
  A janela e de **3 dias** no workspace Hobby e **7 dias** no Pro ou superior.
- O restore cria uma **nova instancia** no estado de um instante passado; e
  possivel valida-la antes de apontar os servicos para ela.
- Bancos no **plano Free de compute nao tem** PITR nem export logico pelo
  painel; e preciso usar `pg_dump` local ou fazer upgrade.
- Export logico pelo painel: `Create export` gera `.dir.tar.gz` e o Render
  mantem os exports por **7 dias**, independentemente do plano.
- A documentacao recomenda PITR (nao o export) para recuperacao de perda de
  dados recente.

**NÃO CONFERIDO:** o plano/workspace real deste projeto no Render e a
disponibilidade de PITR/Cron na conta. A documentacao descreve os recursos, mas
nao foi possivel inspecionar a conta. Antes de depender de PITR, confirme no
Dashboard o plano do banco e a janela exibida em **Recovery**.

## 6. Snapshots do Elasticsearch

O indice e **derivado e reconstruivel** a partir do PostgreSQL; o snapshot e
uma conveniencia para reduzir o tempo de recuperacao, nao a fonte de verdade.

### Compose de producao (VPS)

`docker-compose.prod.yml` monta o volume `elasticsearch_snapshots` em
`/usr/share/elasticsearch/snapshots` e define
`path.repo=/usr/share/elasticsearch/snapshots`. O repositorio precisa ser
registrado uma vez:

```bash
# dentro do container ou via API autenticada
curl -X PUT "$ELASTICSEARCH_URL/_snapshot/forja_backups" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"fs","settings":{"location":"/usr/share/elasticsearch/snapshots","compress":true}}'

curl -X PUT "$ELASTICSEARCH_URL/_snapshot/forja_backups/snap-$(date -u +%Y%m%dT%H%M%SZ)?wait_for_completion=true" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY"
```

O volume precisa estar em storage persistente e com backup externo (o snapshot
no mesmo host nao protege contra perda do host). Restauracao:

```bash
curl -X POST "$ELASTICSEARCH_URL/_snapshot/forja_backups/<snapshot>/_restore?wait_for_completion=true" \
  -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"indices":"forja_products_v*","ignore_unavailable":true}'
```

Depois valide o alias (`GET _alias/forja_products`) e rode `reconcile`.

### Elastic Cloud

O Elastic Cloud faz snapshots gerenciados do deployment. A restauracao e feita
pelo painel/API do provedor para um deployment ou indice; confirme a retencao
no contrato. Como o indice e reconstruivel, o caminho mais simples apos uma
perda total e criar o indice versionado com
`python -m app.modules.search.interface.cli reindex`.

### Reconstrucao a partir do PostgreSQL

```bash
docker compose exec backend python -m app.modules.search.interface.cli reindex
docker compose exec backend python -m app.modules.search.interface.cli reconcile
```

O `reindex` cria o indice versionado, valida a contagem contra o PostgreSQL e
troca o alias atomicamente. Se o Elasticsearch estiver fora, a API continua
com o fallback textual do PostgreSQL.

## 7. Limitacoes e riscos

- O backup local usa o superusuario de bootstrap. Em producao, use uma role
  dedicada com `BYPASSRLS` ou o backup gerenciado; nunca exponha o bootstrap.
- Dumps nao sao criptografados pelo script. Guarde em volume/bucket com
  criptografia e acesso restrito; trate como dado pessoal (LGPD).
- O drill restaura no mesmo cluster; ele nao prova recuperacao de perda do
  host. Para isso, teste tambem em outra instancia/regiao.
- O tempo de restore cresce com o banco; o script carrega o dump via stdin e
  nao usa `--jobs` (formato custom de arquivo unico).
- Backups do Render e snapshots do Elastic Cloud dependem do plano contratado;
  os itens marcados NÃO CONFERIDO acima precisam de validacao na conta.
