# Modelo de Atributos de Produto — Catálogo Admin

> Documento da Fase 9-a, atualizado com correções pontuais. O schema atual inclui
> `DRAFT` no `CHECK` de `products.status` (migration 0018) e a API admin descrita
> em `docs/CATALOG_ADMIN.md`; o estado consolidado está em `docs/STATUS.md`.

---

## 1. Auditoria do Estado Atual (Passo 1)

### 1.1 Tabela `products` — colunas atuais

| Coluna | Tipo | Nulabilidade | Limite | Índices / Constraints |
|--------|------|--------------|--------|----------------------|
| `id` | `uuid` | NOT NULL | — | PK, `gen_random_uuid()` |
| `category_id` | `uuid` | NOT NULL | — | FK → `categories.id` (RESTRICT), idx |
| `brand_id` | `uuid` | **NULL** | — | FK → `brands.id` (SET NULL), idx |
| `sku` | `varchar(64)` | NOT NULL | 64 | UNIQUE, GIN trigram |
| `name` | `varchar(200)` | NOT NULL | 200 | GIN trigram |
| `slug` | `varchar(200)` | NOT NULL | 200 | UNIQUE |
| `description` | `text` | **NULL** | — | GIN tsvector (name \|\| description) |
| `status` | `varchar(24)` | NOT NULL | 24 | CHECK (DRAFT/ACTIVE/INACTIVE), default ACTIVE |
| `is_epi` | `boolean` | NOT NULL | — | default false |
| `ca_number` | `varchar(64)` | NULL | 64 | — |
| `ca_valid_until` | `date` | NULL | — | idx parcial (WHERE is_epi) |
| `ncm` | `varchar(8)` | NULL | 8 | — |
| `unit_of_measure` | `varchar(10)` | NULL | 10 | — |
| `weight_kg` | `numeric(10,3)` | NULL | — | CHECK (>0) |
| `min_order_qty` | `integer` | NOT NULL | — | CHECK (>=1), default 1 |
| `base_unit_price` | `numeric(12,2)` | NOT NULL | — | CHECK (>=0) |
| `currency` | `varchar(3)` | NOT NULL | 3 | default 'BRL' |
| `attributes` | `jsonb` | NULL | — | GIN |
| `image_url` | `varchar(500)` | NULL | 500 | — |
| `created_at` / `updated_at` | `timestamptz` | NOT NULL | — | `now()` |

**Observações:**
- `brand_id` é **NULLABLE** (FK SET NULL).
- `description` é **NULLABLE**.
- `name` e `sku` já são NOT NULL.
- `status` já tem default e CHECK.

### 1.2 Produtos que violariam "nome, descrição e marca obrigatórios"

Consulta executada no banco de desenvolvimento (`forja_db`):

```sql
-- Nome vazio/NULL
SELECT sku, name FROM products WHERE name IS NULL OR trim(name) = '';
-- Resultado: 0 linhas

-- Descrição vazia/NULL
SELECT sku, description FROM products WHERE description IS NULL OR trim(description) = '';
-- Resultado: 2 linhas
--   EPI-LUV-002 | NULL
--   EPI-RES-003 | NULL
--   MAQ-PAR-004 | NULL

-- Marca NULL
SELECT sku, brand_id FROM products WHERE brand_id IS NULL;
-- Resultado: 0 linhas
```

**Produtos com descrição ausente (3):**
| SKU | Nome | Marca | Categoria |
|-----|------|-------|-----------|
| EPI-LUV-002 | Luva de Raspa Premium | PROTEC | EPIs |
| EPI-RES-003 | Respirador PFF2 | PROTEC | EPIs |
| MAQ-PAR-004 | Parafusadeira de Impacto 20V | NORTON | Máquinas e Ferramentas |

**Conclusão:** Não é seguro aplicar `NOT NULL` em `description` nem em `brand_id` sem antes preencher esses valores. O `name` já é NOT NULL e não há violações.

### 1.3 Modelo da marca

- **Entidade separada** (`brands` table) com `id` (uuid), `name` (unique), `slug` (unique).
- Relacionamento `products.brand_id` → `brands.id` (FK, SET NULL).
- Marcas são **fictícias/controladas** (seed), não texto livre.
- 8 marcas atuais: PROTEC, NORTON, VULCANO, AEGIS, GUARDIAN, FERRUM, TITAN, SENTINEL.

### 1.4 Categorias existentes (slugs)

```
epis
protecao-cabeca
protecao-visual
protecao-maos
protecao-respiratoria
protecao-auditiva
protecao-pes
protecao-quedas
maquinas-e-ferramentas
ferramentas-eletricas
maquinas-estacionarias
```

---

## 2. Domínio Puro — Definição de Atributos (Passo 2)

### 2.1 Definição de Atributo (`AttributeDefinition`)

```python
class AttributeType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    ENUM = "enum"
    BOOLEAN = "boolean"

@dataclass(frozen=True, kw_only=True)
class AttributeDefinition:
    key: str                    # slug estável, ex.: "modelo", "cor", "tamanho"
    label: str                  # pt-BR para UI, ex.: "Modelo", "Cor", "Tamanho"
    type: AttributeType
    unit: str | None = None     # ex.: "W", "V", "kg", "mm"
    options: list[EnumOption] | None = None  # para ENUM: [{key, label}, ...]
    scope: Scope = Scope.GLOBAL # GLOBAL ou lista de category_slugs
    section: str = "geral"      # agrupamento visual no formulário
    display_order: int = 0      # ordenação dentro da seção
    required: bool = False      # se True, validação exige preenchimento
    min_value: float | None = None  # para NUMBER
    max_value: float | None = None  # para NUMBER
    max_length: int | None = None   # para TEXT
```

### 2.2 Validador/Normalizador de Valores

Regras:
1. **Chave desconhecida** → erro
2. **Chave fora do escopo da categoria** → erro
3. **Tipo incorreto** → erro
4. **Número fora de intervalo** → erro
5. **Enum com opção inválida** → erro
6. **Texto acima do limite** → erro
7. **Valores vazios** (`""`, whitespace only, `null`, lista vazia) → **descartados** da saída normalizada
8. **Texto simples** → sem HTML, trim

### 2.3 Validação de Obrigatórios do Produto

- `name`: não vazio, trim, 1–200 chars
- `description`: não vazio, trim, 1–2000 chars (ajustável)
- `brand_id`: deve existir em `brands` (não vazio)

---

## 3. Persistência e Migration (Passo 3)

### 3.1 Nova tabela: `product_attribute_definitions`

```sql
CREATE TABLE product_attribute_definitions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key varchar(64) NOT NULL UNIQUE,
    label varchar(100) NOT NULL,
    type varchar(16) NOT NULL CHECK (type IN ('text','number','enum','boolean')),
    unit varchar(20),
    options jsonb,  -- [{key, label}, ...] para enum
    scope jsonb NOT NULL DEFAULT '["global"]',  -- array de category_slugs ou ["global"]
    section varchar(50) NOT NULL DEFAULT 'geral',
    display_order integer NOT NULL DEFAULT 0,
    required boolean NOT NULL DEFAULT false,
    min_value numeric,
    max_value numeric,
    max_length integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

### 3.2 Coluna `attributes` em `products`

- Já existe como `JSONB` (nullable).
- Armazena apenas chaves definidas em `product_attribute_definitions`.
- Exemplo: `{"modelo": "XYZ-100", "cor": "azul", "potencia_w": 850}`.

### 3.3 Constraints NOT NULL

**NÃO APLICADAS** nesta fase (aguardando preenchimento dos 3 produtos sem descrição).
- `description` → pendente
- `brand_id` → pendente (embora seed já preencha, FK permite NULL)

---

## 4. Seed das Definições (Passo 4)

### 4.1 Dicionário Versionado (único local de rótulos/opções)

Arquivo: `backend/app/seed_data/attribute_definitions.json`

```json
{
  "version": 1,
  "definitions": [
    {"key": "modelo", "label": "Modelo", "type": "text", "scope": ["global"], "section": "identificacao", "display_order": 10},
    {"key": "cor", "label": "Cor", "type": "text", "scope": ["global"], "section": "identificacao", "display_order": 20},
    {"key": "tamanho", "label": "Tamanho", "type": "text", "scope": ["global"], "section": "identificacao", "display_order": 30},
    {"key": "material", "label": "Material", "type": "text", "scope": ["global"], "section": "tecnico", "display_order": 10},
    {"key": "peso_kg", "label": "Peso (kg)", "type": "number", "unit": "kg", "scope": ["global"], "section": "tecnico", "display_order": 20, "min_value": 0.001, "max_value": 10000},
    {"key": "unidade_venda", "label": "Unidade de Venda", "type": "text", "scope": ["global"], "section": "comercial", "display_order": 10},
    {"key": "tamanho_luvas", "label": "Tamanho (Luvas)", "type": "enum", "options": [{"key":"P","label":"P"},{"key":"M","label":"M"},{"key":"G","label":"G"},{"key":"GG","label":"GG"}], "scope": ["protecao-maos"], "section": "ajuste", "display_order": 10},
    {"key": "tamanho_botas", "label": "Tamanho (Botas)", "type": "enum", "options": [{"key":"35","label":"35"},{"key":"36","label":"36"},{"key":"37","label":"37"},{"key":"38","label":"38"},{"key":"39","label":"39"},{"key":"40","label":"40"},{"key":"41","label":"41"},{"key":"42","label":"42"},{"key":"43","label":"43"},{"key":"44","label":"44"},{"key":"45","label":"45"},{"key":"46","label":"46"}], "scope": ["protecao-pes"], "section": "ajuste", "display_order": 10},
    {"key": "cor_capacete", "label": "Cor (Capacete)", "type": "enum", "options": [{"key":"branco","label":"Branco"},{"key":"amarelo","label":"Amarelo"},{"key":"azul","label":"Azul"},{"key":"vermelho","label":"Vermelho"},{"key":"verde","label":"Verde"},{"key":"laranja","label":"Laranja"},{"key":"preto","label":"Preto"}], "scope": ["protecao-cabeca"], "section": "identificacao", "display_order": 5},
    {"key": "cor_coleta", "label": "Cor (Colete)", "type": "enum", "options": [{"key":"amarelo","label":"Amarelo"},{"key":"laranja","label":"Laranja"},{"key":"verde","label":"Verde"}], "scope": ["epis"], "section": "identificacao", "display_order": 5},
    {"key": "potencia_w", "label": "Potência (W)", "type": "number", "unit": "W", "scope": ["ferramentas-eletricas", "maquinas-estacionarias"], "section": "tecnico", "display_order": 10, "min_value": 10, "max_value": 50000},
    {"key": "tensao_v", "label": "Tensão (V)", "type": "enum", "options": [{"key":"110","label":"110V"},{"key":"220","label":"220V"},{"key":"bivolt","label":"Bivolt"}], "scope": ["ferramentas-eletricas", "maquinas-estacionarias"], "section": "tecnico", "display_order": 20},
    {"key": "ca", "label": "CA (Certificado de Aprovação)", "type": "text", "scope": ["epis"], "section": "conformidade", "display_order": 10, "max_length": 64}
  ]
}
```

### 4.2 Regras do Seed

- **Idempotente**: `ON CONFLICT (key) DO UPDATE` mantendo `label`, `type`, `options`, `scope`, `section`, `display_order`, `required`, `min_value`, `max_value`, `max_length`, `unit`.
- **Sem valores técnicos inventados**: CA é apenas texto opcional para o admin preencher.
- **Rótulos centralizados** no JSON → facilita tradução na Fase 9-b.

---

## 5. Como Adicionar Nova Definição

1. Editar `backend/app/seed_data/attribute_definitions.json` adicionando entrada no array `definitions`.
2. Incrementar `version`.
3. Rodar seed: `python -m app.infrastructure.db.seeds_attribute_definitions`.
4. Verificar: `SELECT * FROM product_attribute_definitions WHERE key = 'nova_chave';`.
5. A validação de domínio passa a aceitar a nova chave automaticamente.

---

## 6. Checklist de Checagens Finais (Passo 5)

- [x] Ruff check
- [x] Ruff format
- [x] Mypy strict
- [x] Import-linter (4 contracts)
- [x] Testes unitários domínio + aplicação
- [x] Migration aplicada + `alembic check` limpo
- [x] Seed idempotente (2 execuções)
- [x] Backup pg_dump antes da migration

---

## 7. Relatório — Produtos Violando Obrigatórios

| SKU | Campo Faltante | Ação Necessária |
|-----|----------------|-----------------|
| EPI-LUV-002 | description | Preencher descrição no seed ou admin |
| EPI-RES-003 | description | Preencher descrição no seed ou admin |
| MAQ-PAR-004 | description | Preencher descrição no seed ou admin |

**NOT NULL aplicado?** NÃO — aguardando preenchimento dos 3 produtos acima.