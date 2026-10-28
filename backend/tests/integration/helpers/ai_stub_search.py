"""Stub da busca para testes de integracao das portas de IA.

Substitui o `SearchProducts` real (que exigiria Elasticsearch/pgvector) sem
tocar rede: devolve ids do Postgres de acordo com a query, deixando a
hidratacao/preco para o `ProductReader` real.
"""

from __future__ import annotations

import uuid

from app.modules.search.application.ports import SearchQuery
from app.modules.search.application.search import SearchResultItem, SearchResultPage


class StubSearchProducts:
    def __init__(self, ids: list[uuid.UUID] | None = None) -> None:
        self.ids = ids or []

    async def run(self, *, query: SearchQuery, auth: object) -> SearchResultPage:
        items = [
            SearchResultItem(
                id=product_id,
                sku="STUB",
                name="Stub",
                slug="stub",
                status="ACTIVE",
                is_epi=False,
                ca_status="NOT_APPLICABLE",
                category_id=uuid.uuid4(),
                category_name="Stub",
                category_slug="stub",
                brand_id=None,
                brand_name=None,
                brand_slug=None,
                base_unit_price=None,
                currency="BRL",
                min_order_qty=1,
                price_on_request=True,
                image_url="",
                image_alt="Stub",
                content_locale="pt-BR",
            )
            for product_id in self.ids
        ]
        return SearchResultPage(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            pages=1,
            search_mode="stub",
        )
