"""Casos de uso para administração de traduções de produto (camada de aplicação).

Operações CRUD de traduções armazenadas: visualizar estado, editar manual,
marcar como reviewed. O provedor de tradução (quando habilitado) é invocado
apenas via processo de background (não no request path).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from app.application.i18n import ProductTextTranslation
from app.application.ports.translation import TranslationProvider
from app.application.security import AuthContext, require_role
from app.core.config import Settings
from app.core.errors import AppError
from app.domain.i18n import TranslationStatus, product_source_hash, sanitize_translated_text
from app.modules.catalog.application.ports import CatalogAdminRepository

# ---------------------------------------------------------------------------
# Erros de aplicação
# ---------------------------------------------------------------------------


class AuthorizationError(AppError):
    """Acesso negado (403)."""

    status_code = 403
    title = "Forbidden"
    code = "forbidden"


class ValidationError(AppError):
    """Erro de validação (422)."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "validation_error"


class NotFoundError(AppError):
    """Não encontrado (404)."""

    status_code = 404
    title = "Not Found"
    code = "not_found"


# ---------------------------------------------------------------------------
# Port de persistência para traduções
# ---------------------------------------------------------------------------


class TranslationAdminRepository(Protocol):
    """Persistência de escrita/leitura de traduções de produto (role forja_admin)."""

    async def get_translation(
        self, product_id: uuid.UUID, locale: str
    ) -> tuple[ProductTextTranslation, str] | None:
        """Obtém tradução existente e seu status."""

    async def upsert_translation(
        self,
        *,
        product_id: uuid.UUID,
        locale: str,
        name: str | None,
        description: str | None,
        attributes: dict[str, object] | None,
        status: TranslationStatus,
        source_hash: str,
    ) -> ProductTextTranslation:
        """Cria ou atualiza tradução."""

    async def list_product_translations(
        self, product_id: uuid.UUID
    ) -> list[tuple[str, ProductTextTranslation, str, str, datetime | None]]:
        """Lista todas as traduções de um produto.

        Retorna tuplas: (locale, translation, status, source_hash, translated_at)
        """


# ---------------------------------------------------------------------------
# Implementação SQLAlchemy
# ---------------------------------------------------------------------------


class SqlAlchemyTranslationAdminRepository:
    """Implementação sobre ORM + UoW (sem tenant)."""

    def __init__(self, uow_factory: Any) -> None:
        self._uow_factory = uow_factory

    async def get_translation(
        self, product_id: uuid.UUID, locale: str
    ) -> tuple[ProductTextTranslation, str] | None:
        from sqlalchemy import text

        stmt = text(
            "SELECT name, description, attributes, status, source_hash, translated_at "
            "FROM product_translations WHERE product_id = :product_id AND locale = :locale"
        )
        async with self._uow_factory.begin() as uow:
            row = (
                await uow.session.execute(
                    stmt, {"product_id": product_id, "locale": locale}
                )
            ).first()
            await uow.commit()
            if row is None:
                return None
            return (
                ProductTextTranslation(
                    name=row.name,
                    description=row.description,
                    attributes=row.attributes,
                ),
                row.status,
            )

    async def upsert_translation(
        self,
        *,
        product_id: uuid.UUID,
        locale: str,
        name: str | None,
        description: str | None,
        attributes: dict[str, object] | None,
        status: TranslationStatus,
        source_hash: str,
    ) -> ProductTextTranslation:
        from sqlalchemy import text

        stmt = text(
            "INSERT INTO product_translations "
            "(product_id, locale, name, description, attributes, source_hash, "
            "status, translated_at) VALUES "
            "(:product_id, :locale, :name, :description, CAST(:attributes AS jsonb), "
            ":source_hash, :status, :translated_at) "
            "ON CONFLICT (product_id, locale) DO UPDATE SET "
            "name = EXCLUDED.name, description = EXCLUDED.description, "
            "attributes = EXCLUDED.attributes, source_hash = EXCLUDED.source_hash, "
            "status = EXCLUDED.status, translated_at = EXCLUDED.translated_at, "
            "updated_at = now() RETURNING name, description, attributes, "
            "status, source_hash, translated_at"
        )
        async with self._uow_factory.begin() as uow:
            row = (
                await uow.session.execute(
                    stmt,
                    {
                        "product_id": product_id,
                        "locale": locale,
                        "name": name,
                        "description": description,
                        "attributes": attributes,
                        "source_hash": source_hash,
                        "status": status.value,
                        "translated_at": datetime.now(UTC),
                    },
                )
            ).first()
            await uow.commit()
            if row is None:
                raise ValueError("upsert_translation returned no row")
            return ProductTextTranslation(
                name=row.name,
                description=row.description,
                attributes=row.attributes,
            )

    async def list_product_translations(
        self, product_id: uuid.UUID
    ) -> list[tuple[str, ProductTextTranslation, str, str, datetime | None]]:
        from sqlalchemy import text

        stmt = text(
            "SELECT locale, name, description, attributes, status, source_hash, translated_at "
            "FROM product_translations WHERE product_id = :product_id ORDER BY locale"
        )
        async with self._uow_factory.begin() as uow:
            rows = (
                await uow.session.execute(stmt, {"product_id": product_id})
            ).all()
            await uow.commit()
        return [
            (
                row.locale,
                ProductTextTranslation(
                    name=row.name,
                    description=row.description,
                    attributes=row.attributes,
                ),
                row.status,
                row.source_hash,
                row.translated_at,
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class TranslationAdminView:
    """Visão administrativa de uma tradução de produto."""

    product_id: uuid.UUID
    locale: str
    name: str | None
    description: str | None
    attributes: dict[str, object] | None
    status: str
    source_hash: str
    translated_at: datetime | None
    is_stale: bool


@dataclass(frozen=True, kw_only=True)
class TranslationUpdateInput:
    """Entrada para editar tradução manualmente."""

    name: str | None = None
    description: str | None = None
    attributes: dict[str, object] | None = None
    mark_reviewed: bool = False


# ---------------------------------------------------------------------------
# Casos de uso
# ---------------------------------------------------------------------------


class GetProductTranslations:
    """Lista todas as traduções de um produto com status stale calculado."""

    def __init__(
        self,
        *,
        repository: TranslationAdminRepository,
        catalog_repository: CatalogAdminRepository,
    ) -> None:
        self._repository = repository
        self._catalog_repository = catalog_repository

    async def execute(self, auth: AuthContext, product_id: uuid.UUID) -> list[TranslationAdminView]:
        require_role(auth, "ADMIN")

        # Verifica se produto existe
        product = await self._catalog_repository.get(product_id)
        if product is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")

        # Busca todas as traduções com metadados completos
        rows = await self._repository.list_product_translations(product_id)

        result: list[TranslationAdminView] = []
        for locale, trans, status, source_hash, translated_at in rows:
            is_stale = product_source_hash(
                name=product.name,
                description=product.description,
                attributes=product.attributes,
            ) != source_hash
            result.append(
                TranslationAdminView(
                    product_id=product_id,
                    locale=locale,
                    name=trans.name,
                    description=trans.description,
                    attributes=trans.attributes,
                    status=status,
                    source_hash=source_hash,
                    translated_at=translated_at,
                    is_stale=is_stale,
                )
            )

        return result


class UpdateTranslation:
    """Edita manualmente uma tradução e opcionalmente marca como reviewed."""

    def __init__(
        self,
        *,
        repository: TranslationAdminRepository,
        catalog_repository: CatalogAdminRepository,
        translation_provider: TranslationProvider,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._catalog_repository = catalog_repository
        self._translation_provider = translation_provider
        self._settings = settings

    async def execute(
        self,
        auth: AuthContext,
        product_id: uuid.UUID,
        locale: str,
        input_data: TranslationUpdateInput,
    ) -> TranslationAdminView:
        require_role(auth, "ADMIN")

        product = await self._get_product_or_404(product_id)
        self._validate_locale(locale)

        current_result = await self._repository.get_translation(product_id, locale)
        if current_result is not None:
            current, current_status = current_result
        else:
            current, current_status = None, None
        name, description, attributes = self._merge_values(input_data, current)
        name, description, attributes = self._sanitize_values(name, description, attributes)
        status = self._determine_status(input_data, current_status)

        source_hash = product_source_hash(
            name=product.name,
            description=product.description,
            attributes=product.attributes,
        )

        await self._repository.upsert_translation(
            product_id=product_id,
            locale=locale,
            name=name,
            description=description,
            attributes=attributes,
            status=status,
            source_hash=source_hash,
        )

        if self._translation_provider.enabled:
            pass  # Enfileirar retradução via outbox/queue

        is_stale = product_source_hash(
            name=product.name,
            description=product.description,
            attributes=product.attributes,
        ) != source_hash

        return TranslationAdminView(
            product_id=product_id,
            locale=locale,
            name=name,
            description=description,
            attributes=attributes,
            status=status.value,
            source_hash=source_hash,
            translated_at=datetime.now(UTC),
            is_stale=is_stale,
        )

    async def _get_product_or_404(self, product_id: uuid.UUID) -> Any:
        product = await self._catalog_repository.get(product_id)
        if product is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")
        return product

    def _validate_locale(self, locale: str) -> None:
        if locale not in self._settings.supported_locale_list:
            raise ValidationError(f"Locale {locale} não suportado")
        if locale == self._settings.default_locale:
            raise ValidationError("Não é possível editar tradução do idioma de origem (pt-BR)")

    def _merge_values(
        self,
        input_data: TranslationUpdateInput,
        current: ProductTextTranslation | None,
    ) -> tuple[str | None, str | None, dict[str, object] | None]:
        name = input_data.name
        if name is None and current is not None:
            name = current.name
        description = input_data.description
        if description is None and current is not None:
            description = current.description
        attributes = input_data.attributes
        if attributes is None and current is not None:
            attributes = current.attributes
        return name, description, attributes

    def _sanitize_values(
        self,
        name: str | None,
        description: str | None,
        attributes: dict[str, object] | None,
    ) -> tuple[str | None, str | None, dict[str, object] | None]:
        if name is not None:
            name = sanitize_translated_text(name, max_length=200)
        if description is not None:
            description = sanitize_translated_text(description, max_length=4000)
        if attributes is not None:
            sanitized_attrs: dict[str, object] = {}
            for k, v in attributes.items():
                if isinstance(v, str):
                    sanitized_attrs[k] = sanitize_translated_text(v, max_length=4000)
                else:
                    sanitized_attrs[k] = v
            attributes = sanitized_attrs if sanitized_attrs else None
        return name, description, attributes

    def _determine_status(
        self,
        input_data: TranslationUpdateInput,
        current_status: str | None,
    ) -> TranslationStatus:
        if input_data.mark_reviewed:
            return TranslationStatus.REVIEWED
        if current_status == TranslationStatus.REVIEWED.value and not input_data.mark_reviewed:
            return TranslationStatus.REVIEWED
        return TranslationStatus.MACHINE
