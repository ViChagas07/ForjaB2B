"""Casos de uso para administração de produtos (camada de aplicação).

Reutiliza validação de domínio e delega persistência ao repositório.
Emite eventos na outbox de busca para sincronização do Elasticsearch.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.application.security import AuthContext, require_role
from app.core.errors import AppError
from app.domain.product_attributes import (
    AttributeRegistry,
    normalize_and_validate_attributes,
)
from app.modules.catalog.application.ports import (
    AuditLogPort,
    CatalogAdminRepository,
    SearchOutboxPort,
)
from app.modules.catalog.domain.product_admin import (
    CreateProductInput,
    ProductAdminView,
    ProductListFilters,
    ProductPage,
    PublishProductInput,
    SkuAlreadyExistsError,
    SlugAlreadyExistsError,
    UpdateProductInput,
    apply_update_to_product,
    validate_and_normalize_create_input,
    validate_and_normalize_update_input,
)

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


class ConflictError(AppError):
    """Conflito (409) - ex: concorrência otimista."""

    status_code = 409
    title = "Conflict"
    code = "conflict"


class NotFoundError(AppError):
    """Não encontrado (404)."""

    status_code = 404
    title = "Not Found"
    code = "not_found"


# ---------------------------------------------------------------------------
# Casos de uso
# ---------------------------------------------------------------------------


class CreateProduct:
    """Cria um novo produto (apenas forja_admin)."""

    def __init__(
        self,
        *,
        repository: CatalogAdminRepository,
        outbox: SearchOutboxPort,
        audit: AuditLogPort,
        registry: AttributeRegistry,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._audit = audit
        self._registry = registry

    async def execute(
        self,
        auth: AuthContext,
        input_data: CreateProductInput,
    ) -> ProductAdminView:
        require_role(auth, "ADMIN")  # papel de empresa ADMIN = administrador do catálogo

        existing_skus = await self._repository.get_all_skus()
        existing_slugs = await self._repository.get_all_slugs()

        try:
            slug, normalized_attrs = validate_and_normalize_create_input(
                input_data, self._registry, existing_skus, existing_slugs
            )
        except SkuAlreadyExistsError as exc:
            raise ConflictError(str(exc)) from exc
        except SlugAlreadyExistsError as exc:
            raise ConflictError(str(exc)) from exc
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        # Valida categoria e marca existem
        category = await self._repository.get_category(input_data.category_id)
        if category is None:
            raise NotFoundError(f"Categoria {input_data.category_id} não encontrada")

        brand = await self._repository.get_brand(input_data.brand_id)
        if brand is None:
            raise NotFoundError(f"Marca {input_data.brand_id} não encontrada")

        # Re-valida atributos com category_slug correto
        normalized_attrs = normalize_and_validate_attributes(
            input_data.attributes or {}, self._registry, category.slug
        )

        now = datetime.now(UTC)
        product = ProductAdminView(
            id=uuid.uuid4(),
            sku=input_data.sku,
            name=input_data.name.strip(),
            slug=slug,
            description=input_data.description.strip(),
            status="ACTIVE",
            category_id=input_data.category_id,
            category_name=category.name,
            category_slug=category.slug,
            brand_id=input_data.brand_id,
            brand_name=brand.name,
            brand_slug=brand.slug,
            is_epi=input_data.is_epi,
            ca_number=input_data.ca_number,
            ca_valid_until=input_data.ca_valid_until,
            ncm=input_data.ncm,
            unit_of_measure=input_data.unit_of_measure,
            weight_kg=input_data.weight_kg,
            min_order_qty=input_data.min_order_qty,
            base_unit_price=input_data.base_unit_price,
            currency=input_data.currency,
            image_url=input_data.image_url,
            attributes=normalized_attrs if normalized_attrs else None,
            version=int(now.timestamp() * 1000),
            created_at=now,
            updated_at=now,
            created_by=auth.user_id,
            updated_by=auth.user_id,
        )

        created = await self._repository.create(product)

        # Emite evento na outbox de busca
        await self._outbox.emit_upsert(
            product_id=created.id,
            version=created.version,
        )

        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="catalog.product.created",
            resource="product",
            resource_id=created.id,
            details={"sku": created.sku},
        )

        return created


class GetProductAdmin:
    """Obtém um produto para administração (apenas forja_admin)."""

    def __init__(self, *, repository: CatalogAdminRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext, product_id: uuid.UUID) -> ProductAdminView:
        require_role(auth, "ADMIN")
        product = await self._repository.get(product_id)
        if product is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")
        return product


class ListProductsAdmin:
    """Lista produtos com filtros e paginação (apenas forja_admin)."""

    def __init__(self, *, repository: CatalogAdminRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        auth: AuthContext,
        filters: ProductListFilters,
    ) -> ProductPage:
        require_role(auth, "ADMIN")

        # Limite máximo de paginação
        if filters.page_size > 100:
            filters = ProductListFilters(
                q=filters.q,
                category_id=filters.category_id,
                status=filters.status,
                page=filters.page,
                page_size=100,
            )

        return await self._repository.list(filters)


class UpdateProduct:
    """Atualiza um produto (PATCH) com concorrência otimista (apenas forja_admin)."""

    def __init__(
        self,
        *,
        repository: CatalogAdminRepository,
        outbox: SearchOutboxPort,
        audit: AuditLogPort,
        registry: AttributeRegistry,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._audit = audit
        self._registry = registry

    async def execute(
        self,
        auth: AuthContext,
        product_id: uuid.UUID,
        input_data: UpdateProductInput,
    ) -> ProductAdminView:
        require_role(auth, "ADMIN")

        current = await self._repository.get(product_id)
        if current is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")

        self._check_optimistic_lock(input_data, current)

        category_slug = await self._resolve_category_slug(input_data, current)

        await self._resolve_brand(input_data, current)

        normalized_attrs = self._normalize_attributes(input_data, category_slug, current.sku)

        if normalized_attrs is not None and input_data.category_id is not None:
            normalized_attrs = normalize_and_validate_attributes(
                input_data.attributes or {}, self._registry, category_slug
            )

        # Slugs existentes para desambiguar o slug ao renomear
        existing_slugs = await self._repository.get_all_slugs()

        updated = apply_update_to_product(
            current, input_data, normalized_attrs, self._registry, category_slug, existing_slugs
        )
        updated = ProductAdminView(
            **{**vars(updated), "updated_by": auth.user_id, "category_name": current.category_name}
        )

        updated = await self._apply_category_brand_changes(input_data, current, updated)

        saved = await self._repository.update(updated)

        await self._outbox.emit_upsert(
            product_id=saved.id,
            version=saved.version,
        )

        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="catalog.product.updated",
            resource="product",
            resource_id=saved.id,
            details={"sku": saved.sku},
        )

        return saved

    def _check_optimistic_lock(
        self, input_data: UpdateProductInput, current: ProductAdminView
    ) -> None:
        if input_data.version != current.version:
            raise ConflictError(
                "Registro foi alterado por outro usuário; recarregue e tente novamente"
            )

    async def _resolve_category_slug(
        self, input_data: UpdateProductInput, current: ProductAdminView
    ) -> str:
        category_slug = current.category_slug
        if input_data.category_id is not None and input_data.category_id != current.category_id:
            category = await self._repository.get_category(input_data.category_id)
            if category is None:
                raise NotFoundError(f"Categoria {input_data.category_id} não encontrada")
            category_slug = category.slug
        return category_slug

    async def _resolve_brand(
        self, input_data: UpdateProductInput, current: ProductAdminView
    ) -> None:
        if input_data.brand_id is not None and input_data.brand_id != current.brand_id:
            brand = await self._repository.get_brand(input_data.brand_id)
            if brand is None:
                raise NotFoundError(f"Marca {input_data.brand_id} não encontrada")

    def _normalize_attributes(
        self,
        input_data: UpdateProductInput,
        category_slug: str,
        current_sku: str,
    ) -> dict[str, Any] | None:
        try:
            return validate_and_normalize_update_input(
                input_data, self._registry, category_slug, current_sku
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

    async def _apply_category_brand_changes(
        self,
        input_data: UpdateProductInput,
        current: ProductAdminView,
        updated: ProductAdminView,
    ) -> ProductAdminView:
        if input_data.category_id is not None and input_data.category_id != current.category_id:
            category = await self._repository.get_category(input_data.category_id)
            if category:
                updated = ProductAdminView(
                    **{
                        **vars(updated),
                        "category_name": category.name,
                        "category_slug": category.slug,
                    }
                )

        if input_data.brand_id is not None and input_data.brand_id != current.brand_id:
            brand = await self._repository.get_brand(input_data.brand_id)
            if brand:
                updated = ProductAdminView(
                    **{**vars(updated), "brand_name": brand.name, "brand_slug": brand.slug}
                )
        return updated


class PublishProduct:
    """Publica um produto (DRAFT -> ACTIVE) (apenas forja_admin)."""

    def __init__(
        self,
        *,
        repository: CatalogAdminRepository,
        outbox: SearchOutboxPort,
        audit: AuditLogPort,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._audit = audit

    async def execute(
        self,
        auth: AuthContext,
        product_id: uuid.UUID,
        input_data: PublishProductInput,
    ) -> ProductAdminView:
        require_role(auth, "ADMIN")

        current = await self._repository.get(product_id)
        if current is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")

        if input_data.version != current.version:
            raise ConflictError(
                "Registro foi alterado por outro usuário; recarregue e tente novamente"
            )

        if current.status == "ACTIVE":
            return current  # idempotente

        updated = ProductAdminView(
            **{
                **vars(current),
                "status": "ACTIVE",
                "version": current.version,
                "updated_at": current.updated_at,
                "updated_by": auth.user_id,
            }
        )

        saved = await self._repository.update(updated)

        # Emite evento na outbox de busca
        await self._outbox.emit_upsert(
            product_id=saved.id,
            version=saved.version,
        )

        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="catalog.product.published",
            resource="product",
            resource_id=saved.id,
            details={"sku": saved.sku},
        )

        return saved


class UnpublishProduct:
    """Despublica um produto (ACTIVE -> DRAFT) (apenas forja_admin)."""

    def __init__(
        self,
        *,
        repository: CatalogAdminRepository,
        outbox: SearchOutboxPort,
        audit: AuditLogPort,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._audit = audit

    async def execute(
        self,
        auth: AuthContext,
        product_id: uuid.UUID,
        input_data: PublishProductInput,
    ) -> ProductAdminView:
        require_role(auth, "ADMIN")

        current = await self._repository.get(product_id)
        if current is None:
            raise NotFoundError(f"Produto {product_id} não encontrado")

        if input_data.version != current.version:
            raise ConflictError(
                "Registro foi alterado por outro usuário; recarregue e tente novamente"
            )

        if current.status == "DRAFT":
            return current  # idempotente

        updated = ProductAdminView(
            **{
                **vars(current),
                "status": "DRAFT",
                "version": current.version,
                "updated_at": current.updated_at,
                "updated_by": auth.user_id,
            }
        )

        saved = await self._repository.update(updated)

        # Emite evento DELETE na outbox (produto despublicado sai do índice)
        await self._outbox.emit_delete(
            product_id=saved.id,
            version=saved.version,
        )

        await self._audit.record(
            company_id=auth.company_id,
            actor_user_id=auth.user_id,
            action="catalog.product.unpublished",
            resource="product",
            resource_id=saved.id,
            details={"sku": saved.sku},
        )

        return saved


class GetAttributeDefinitionsForCategory:
    """Obtém definições de atributo aplicáveis a uma categoria (para formulário)."""

    def __init__(self, *, registry: AttributeRegistry) -> None:
        self._registry = registry

    async def execute(self, category_slug: str) -> list[dict[str, Any]]:
        """Retorna definições como dicts serializáveis para a API."""
        from app.application.product_attributes import AttributeDefinitionSchema

        defs = self._registry.get_for_category(category_slug)
        return [AttributeDefinitionSchema.model_validate(d.__dict__).model_dump() for d in defs]


class ListStaticImages:
    """Lista imagens estáticas disponíveis em /static/catalog/."""

    def __init__(self) -> None:
        pass

    async def execute(self) -> list[dict[str, str]]:
        """Retorna lista de {path, label} das imagens estáticas."""
        from app.domain.catalog_image import CATEGORY_IMAGE_PATHS, GENERIC_IMAGE_PATH

        images = [{"path": GENERIC_IMAGE_PATH, "label": "Genérico (placeholder)"}]
        for slug, path in sorted(CATEGORY_IMAGE_PATHS.items()):
            images.append({"path": path, "label": f"Categoria: {slug}"})
        return images
