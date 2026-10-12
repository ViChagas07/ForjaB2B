CREATE TABLE IF NOT EXISTS product_attribute_definitions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key varchar(64) NOT NULL UNIQUE,
    label varchar(100) NOT NULL,
    type varchar(16) NOT NULL,
    unit varchar(20),
    options jsonb,
    scope jsonb NOT NULL DEFAULT '["global"]'::jsonb,
    section varchar(50) NOT NULL DEFAULT 'geral',
    display_order integer NOT NULL DEFAULT 0,
    required boolean NOT NULL DEFAULT false,
    min_value numeric(12, 3),
    max_value numeric(12, 3),
    max_length integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT product_attribute_definitions_type_check CHECK (type IN ('text', 'number', 'enum', 'boolean'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_product_attribute_definitions_key ON product_attribute_definitions (key);