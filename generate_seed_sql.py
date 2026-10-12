import json
from pathlib import Path

json_path = Path('backend/app/seed_data/attribute_definitions.json')
data = json.loads(json_path.read_text(encoding='utf-8'))

sql_statements = []

for defn in data['definitions']:
    key = defn['key']
    label = defn['label'].replace("'", "''")
    type_ = defn['type']
    unit = defn.get('unit')
    options = defn.get('options')
    scope = defn.get('scope', ['global'])
    section = defn.get('section', 'geral')
    display_order = defn.get('display_order', 0)
    required = defn.get('required', False)
    min_value = defn.get('min_value')
    max_value = defn.get('max_value')
    max_length = defn.get('max_length')
    
    # Properly escape JSON for PostgreSQL
    if unit:
        unit_sql = f"'{unit.replace("'", "''")}'"
    else:
        unit_sql = 'NULL'
    
    if options:
        options_json = json.dumps(options)
        options_sql = f"'{options_json.replace("'", "''")}'::jsonb"
    else:
        options_sql = 'NULL'
    
    scope_json = json.dumps(scope)
    scope_sql = f"'{scope_json.replace("'", "''")}'::jsonb"
    
    section_sql = f"'{section.replace("'", "''")}'"
    
    min_value_sql = str(min_value) if min_value is not None else 'NULL'
    max_value_sql = str(max_value) if max_value is not None else 'NULL'
    max_length_sql = str(max_length) if max_length is not None else 'NULL'
    required_sql = 'true' if required else 'false'
    
    sql = f"""INSERT INTO product_attribute_definitions (key, label, type, unit, options, scope, section, display_order, required, min_value, max_value, max_length, created_at, updated_at) VALUES ('{key}', '{label}', '{type_}', {unit_sql}, {options_sql}, {scope_sql}, {section_sql}, {display_order}, {required_sql}, {min_value_sql}, {max_value_sql}, {max_length_sql}, now(), now()) ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label, type = EXCLUDED.type, unit = EXCLUDED.unit, options = EXCLUDED.options, scope = EXCLUDED.scope, section = EXCLUDED.section, display_order = EXCLUDED.display_order, required = EXCLUDED.required, min_value = EXCLUDED.min_value, max_value = EXCLUDED.max_value, max_length = EXCLUDED.max_length, updated_at = now();"""
    
    sql_statements.append(sql)

output_path = Path('backend/scripts/seed_attribute_definitions.sql')
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text('\n'.join(sql_statements), encoding='utf-8')
print(f"Generated {len(sql_statements)} SQL statements to {output_path}")