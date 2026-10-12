"""Testes unitários do domínio de atributos de produto."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.domain.product_attributes import (
    AttributeDefinition,
    AttributeRegistry,
    AttributeType,
    EnumOption,
    ScopeType,
    ValidationError,
    load_registry_from_json,
    normalize_and_validate_attributes,
    validate_product_required_fields,
)


class TestAttributeDefinition:
    """Testes da definição de atributo."""

    def test_text_validation_ok(self) -> None:
        defn = AttributeDefinition(
            key="modelo",
            label="Modelo",
            type=AttributeType.TEXT,
            max_length=50,
        )
        assert defn.validate_value("ABC-123") == (True, None)
        assert defn.validate_value("") == (True, None)  # vazio é OK (descartado depois)

    def test_text_validation_too_long(self) -> None:
        defn = AttributeDefinition(
            key="modelo",
            label="Modelo",
            type=AttributeType.TEXT,
            max_length=10,
        )
        assert defn.validate_value("A" * 11) == (False, "Texto excede 10 caracteres")

    def test_text_validation_wrong_type(self) -> None:
        defn = AttributeDefinition(
            key="modelo",
            label="Modelo",
            type=AttributeType.TEXT,
        )
        assert defn.validate_value(123) == (False, "Valor deve ser texto, recebido int")

    def test_number_validation_ok(self) -> None:
        defn = AttributeDefinition(
            key="potencia_w",
            label="Potência (W)",
            type=AttributeType.NUMBER,
            min_value=Decimal("10"),
            max_value=Decimal("50000"),
        )
        assert defn.validate_value(1000) == (True, None)
        assert defn.validate_value("850") == (True, None)
        assert defn.validate_value(Decimal("1500.5")) == (True, None)

    def test_number_validation_out_of_range(self) -> None:
        defn = AttributeDefinition(
            key="potencia_w",
            label="Potência (W)",
            type=AttributeType.NUMBER,
            min_value=Decimal("10"),
            max_value=Decimal("50000"),
        )
        assert defn.validate_value(5) == (False, "Valor deve ser >= 10")
        assert defn.validate_value(60000) == (False, "Valor deve ser <= 50000")

    def test_number_validation_wrong_type(self) -> None:
        defn = AttributeDefinition(
            key="potencia_w",
            label="Potência (W)",
            type=AttributeType.NUMBER,
        )
        assert defn.validate_value("abc") == (False, "Valor deve ser numérico, recebido 'abc'")

    def test_enum_validation_ok(self) -> None:
        defn = AttributeDefinition(
            key="tensao_v",
            label="Tensão (V)",
            type=AttributeType.ENUM,
            options=(
                EnumOption(key="110", label="110V"),
                EnumOption(key="220", label="220V"),
                EnumOption(key="bivolt", label="Bivolt"),
            ),
        )
        assert defn.validate_value("110") == (True, None)
        assert defn.validate_value("bivolt") == (True, None)

    def test_enum_validation_invalid_option(self) -> None:
        defn = AttributeDefinition(
            key="tensao_v",
            label="Tensão (V)",
            type=AttributeType.ENUM,
            options=(
                EnumOption(key="110", label="110V"),
                EnumOption(key="220", label="220V"),
            ),
        )
        assert defn.validate_value("380") == (False, "Opção inválida: 380. Válidas: ['110', '220']")

    def test_enum_validation_wrong_type(self) -> None:
        defn = AttributeDefinition(
            key="tensao_v",
            label="Tensão (V)",
            type=AttributeType.ENUM,
            options=(EnumOption(key="110", label="110V"),),
        )
        expected = (
            False,
            "Valor deve ser string (chave da opção), recebido int",
        )
        assert defn.validate_value(110) == expected

    def test_boolean_validation_ok(self) -> None:
        defn = AttributeDefinition(
            key="bivolt",
            label="Bivolt",
            type=AttributeType.BOOLEAN,
        )
        assert defn.validate_value(True) == (True, None)
        assert defn.validate_value(False) == (True, None)

    def test_boolean_validation_wrong_type(self) -> None:
        defn = AttributeDefinition(
            key="bivolt",
            label="Bivolt",
            type=AttributeType.BOOLEAN,
        )
        assert defn.validate_value("true") == (False, "Valor deve ser booleano, recebido str")

    def test_applies_to_category_global(self) -> None:
        defn = AttributeDefinition(
            key="modelo",
            label="Modelo",
            type=AttributeType.TEXT,
            scope_type=ScopeType.GLOBAL,
        )
        assert defn.applies_to_category("protecao-cabeca") is True
        assert defn.applies_to_category("ferramentas-eletricas") is True

    def test_applies_to_category_specific(self) -> None:
        defn = AttributeDefinition(
            key="tamanho_luvas",
            label="Tamanho (Luvas)",
            type=AttributeType.ENUM,
            scope_type=ScopeType.CATEGORIES,
            scope_categories=("protecao-maos",),
        )
        assert defn.applies_to_category("protecao-maos") is True
        assert defn.applies_to_category("protecao-pes") is False


class TestAttributeRegistry:
    """Testes do registry de definições."""

    def test_add_and_get(self) -> None:
        registry = AttributeRegistry()
        defn = AttributeDefinition(
            key="modelo",
            label="Modelo",
            type=AttributeType.TEXT,
        )
        registry.add(defn)
        assert registry.get("modelo") is defn
        assert registry.get("inexistente") is None

    def test_get_for_category_global(self) -> None:
        registry = AttributeRegistry()
        registry.add(
            AttributeDefinition(
                key="modelo",
                label="Modelo",
                type=AttributeType.TEXT,
                scope_type=ScopeType.GLOBAL,
            )
        )
        registry.add(
            AttributeDefinition(
                key="cor", label="Cor", type=AttributeType.TEXT, scope_type=ScopeType.GLOBAL
            )
        )

        result = registry.get_for_category("protecao-cabeca")
        assert len(result) == 2
        keys = {d.key for d in result}
        assert keys == {"modelo", "cor"}

    def test_get_for_category_specific(self) -> None:
        registry = AttributeRegistry()
        registry.add(
            AttributeDefinition(
                key="modelo",
                label="Modelo",
                type=AttributeType.TEXT,
                scope_type=ScopeType.GLOBAL,
            )
        )
        registry.add(
            AttributeDefinition(
                key="tamanho_luvas",
                label="Tamanho (Luvas)",
                type=AttributeType.ENUM,
                scope_type=ScopeType.CATEGORIES,
                scope_categories=("protecao-maos",),
            )
        )

        result = registry.get_for_category("protecao-maos")
        assert len(result) == 2

        result = registry.get_for_category("protecao-pes")
        assert len(result) == 1  # apenas global

    def test_get_for_category_ordering(self) -> None:
        registry = AttributeRegistry()
        registry.add(
            AttributeDefinition(
                key="a",
                label="A",
                type=AttributeType.TEXT,
                section="z",
                display_order=10,
            )
        )
        registry.add(
            AttributeDefinition(
                key="b",
                label="B",
                type=AttributeType.TEXT,
                section="a",
                display_order=5,
            )
        )
        registry.add(
            AttributeDefinition(
                key="c",
                label="C",
                type=AttributeType.TEXT,
                section="a",
                display_order=10,
            )
        )

        result = registry.get_for_category("qualquer")
        keys = [d.key for d in result]
        # Ordenado por section, depois display_order
        assert keys == ["b", "c", "a"]

    def test_get_required_for_category(self) -> None:
        registry = AttributeRegistry()
        registry.add(
            AttributeDefinition(
                key="modelo",
                label="Modelo",
                type=AttributeType.TEXT,
                required=True,
            )
        )
        registry.add(
            AttributeDefinition(key="cor", label="Cor", type=AttributeType.TEXT, required=False)
        )

        required = registry.get_required_for_category("qualquer")
        assert len(required) == 1
        assert required[0].key == "modelo"


class TestNormalizeAndValidateAttributes:
    """Testes de normalização e validação de atributos."""

    def setup_method(self) -> None:
        self.registry = AttributeRegistry()
        self.registry.add(
            AttributeDefinition(
                key="modelo",
                label="Modelo",
                type=AttributeType.TEXT,
                max_length=50,
            )
        )
        self.registry.add(
            AttributeDefinition(
                key="potencia_w",
                label="Potência (W)",
                type=AttributeType.NUMBER,
                min_value=Decimal("10"),
                max_value=Decimal("50000"),
            )
        )
        self.registry.add(
            AttributeDefinition(
                key="tensao_v",
                label="Tensão (V)",
                type=AttributeType.ENUM,
                options=(EnumOption(key="110", label="110V"), EnumOption(key="220", label="220V")),
            )
        )
        self.registry.add(
            AttributeDefinition(
                key="tamanho_luvas",
                label="Tamanho (Luvas)",
                type=AttributeType.ENUM,
                scope_type=ScopeType.CATEGORIES,
                scope_categories=("protecao-maos",),
                options=(EnumOption(key="M", label="M"), EnumOption(key="G", label="G")),
            )
        )

    def test_normalize_valid_attributes(self) -> None:
        raw = {"modelo": "ABC-100", "potencia_w": "850", "tensao_v": "220"}
        result = normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert result == {
            "modelo": "ABC-100",
            "potencia_w": Decimal("850"),
            "tensao_v": "220",
        }

    def test_discard_empty_values(self) -> None:
        raw = {"modelo": "ABC-100", "potencia_w": "", "tensao_v": None, "cor": "  "}
        result = normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert result == {"modelo": "ABC-100"}

    def test_unknown_attribute_error(self) -> None:
        raw = {"modelo": "ABC-100", "inexistente": "valor"}
        with pytest.raises(ValidationError) as exc:
            normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert exc.value.key == "inexistente"
        assert "desconhecido" in str(exc.value)

    def test_out_of_scope_attribute_error(self) -> None:
        raw = {"tamanho_luvas": "M"}
        with pytest.raises(ValidationError) as exc:
            normalize_and_validate_attributes(raw, self.registry, "protecao-pes")
        assert exc.value.key == "tamanho_luvas"
        assert "não se aplica" in str(exc.value)

    def test_in_scope_attribute_ok(self) -> None:
        raw = {"tamanho_luvas": "M"}
        result = normalize_and_validate_attributes(raw, self.registry, "protecao-maos")
        assert result == {"tamanho_luvas": "M"}

    def test_wrong_type_error(self) -> None:
        raw = {"modelo": 123}
        with pytest.raises(ValidationError) as exc:
            normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert exc.value.key == "modelo"

    def test_number_out_of_range_error(self) -> None:
        raw = {"potencia_w": 5}
        with pytest.raises(ValidationError) as exc:
            normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert exc.value.key == "potencia_w"

    def test_enum_invalid_option_error(self) -> None:
        raw = {"tensao_v": "380"}
        with pytest.raises(ValidationError) as exc:
            normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert exc.value.key == "tensao_v"

    def test_text_trimming(self) -> None:
        raw = {"modelo": "  ABC-100  "}
        result = normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert result["modelo"] == "ABC-100"

    def test_number_normalized_to_decimal(self) -> None:
        raw = {"potencia_w": "850"}
        result = normalize_and_validate_attributes(raw, self.registry, "ferramentas-eletricas")
        assert isinstance(result["potencia_w"], Decimal)
        assert result["potencia_w"] == Decimal("850")


class TestValidateProductRequiredFields:
    """Testes de validação dos campos obrigatórios do produto."""

    def test_all_valid(self) -> None:
        errors = validate_product_required_fields("Capacete", "Descrição do produto", "brand-uuid")
        assert errors == []

    def test_missing_name(self) -> None:
        errors = validate_product_required_fields("", "Descrição", "brand-uuid")
        assert "Nome é obrigatório" in errors[0]

    def test_name_only_spaces(self) -> None:
        errors = validate_product_required_fields("   ", "Descrição", "brand-uuid")
        assert "Nome é obrigatório" in errors[0]

    def test_name_too_long(self) -> None:
        errors = validate_product_required_fields("A" * 201, "Descrição", "brand-uuid")
        assert "excede 200" in errors[0]

    def test_missing_description(self) -> None:
        errors = validate_product_required_fields("Capacete", "", "brand-uuid")
        assert "Descrição é obrigatória" in errors[0]

    def test_description_only_spaces(self) -> None:
        errors = validate_product_required_fields("Capacete", "   ", "brand-uuid")
        assert "Descrição é obrigatória" in errors[0]

    def test_description_too_long(self) -> None:
        errors = validate_product_required_fields("Capacete", "A" * 2001, "brand-uuid")
        assert "excede 2000" in errors[0]

    def test_missing_brand(self) -> None:
        errors = validate_product_required_fields("Capacete", "Descrição", "")
        assert "Marca é obrigatória" in errors[0]

    def test_multiple_errors(self) -> None:
        errors = validate_product_required_fields("", "", "")
        assert len(errors) == 3


class TestLoadRegistryFromJSON:
    """Testes de carregamento do registry a partir de JSON."""

    def test_load_from_json(self, tmp_path) -> None:
        json_data = {
            "version": 1,
            "definitions": [
                {
                    "key": "modelo",
                    "label": "Modelo",
                    "type": "text",
                    "scope": ["global"],
                    "section": "identificacao",
                    "display_order": 10,
                    "max_length": 50,
                },
                {
                    "key": "potencia_w",
                    "label": "Potência (W)",
                    "type": "number",
                    "unit": "W",
                    "scope": ["ferramentas-eletricas"],
                    "section": "tecnico",
                    "display_order": 10,
                    "min_value": 10,
                    "max_value": 50000,
                },
                {
                    "key": "tensao_v",
                    "label": "Tensão (V)",
                    "type": "enum",
                    "options": [
                        {"key": "110", "label": "110V"},
                        {"key": "220", "label": "220V"},
                    ],
                    "scope": ["ferramentas-eletricas"],
                    "section": "tecnico",
                    "display_order": 20,
                },
            ],
        }
        json_path = tmp_path / "attrs.json"
        # Write as bytes to avoid encoding issues on Windows
        json_path.write_bytes(json.dumps(json_data, ensure_ascii=False).encode("utf-8"))

        registry = load_registry_from_json(str(json_path))

        assert "modelo" in registry.definitions
        assert "potencia_w" in registry.definitions
        assert "tensao_v" in registry.definitions

        modelo = registry.get("modelo")
        assert modelo.type == AttributeType.TEXT
        assert modelo.max_length == 50
        assert modelo.scope_type == ScopeType.GLOBAL

        potencia = registry.get("potencia_w")
        assert potencia.type == AttributeType.NUMBER
        assert potencia.unit == "W"
        assert potencia.min_value == Decimal("10")
        assert potencia.max_value == Decimal("50000")
        assert potencia.scope_type == ScopeType.CATEGORIES
        assert potencia.scope_categories == ("ferramentas-eletricas",)

        tensao = registry.get("tensao_v")
        assert tensao.type == AttributeType.ENUM
        assert len(tensao.options) == 2
        assert tensao.options[0].key == "110"
        assert tensao.options[0].label == "110V"
