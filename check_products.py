import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

# Use the dev database
admin_url = os.environ.get('DATABASE_ADMIN_URL', 'postgresql+asyncpg://forja_admin:forja_admin@localhost:5432/forja')
engine = create_async_engine(admin_url)

async def check_products():
    async with engine.begin() as conn:
        # Check current products
        result = await conn.execute(text("""
            SELECT id, sku, name, description, brand_id, category_id, status
            FROM products
            ORDER BY sku
        """))
        products = result.fetchall()
        print(f"Total products: {len(products)}")
        for p in products:
            print(f"  SKU: {p.sku}, Name: {p.name}, Desc: {p.description}, Brand: {p.brand_id}, Cat: {p.category_id}, Status: {p.status}")
        
        # Check for violations of mandatory fields
        print()
        print("Products with missing name:")
        result = await conn.execute(text("SELECT sku, name FROM products WHERE name IS NULL OR trim(name) = ''"))
        for p in result.fetchall():
            print(f"  {p.sku}: name={p.name!r}")
        
        print()
        print("Products with missing description:")
        result = await conn.execute(text("SELECT sku, description FROM products WHERE description IS NULL OR trim(description) = ''"))
        for p in result.fetchall():
            print(f"  {p.sku}: description={p.description!r}")
        
        print()
        print("Products with missing brand:")
        result = await conn.execute(text("SELECT sku, brand_id FROM products WHERE brand_id IS NULL"))
        for p in result.fetchall():
            print(f"  {p.sku}: brand_id={p.brand_id}")
        
        # Categories
        print()
        print("Categories:")
        result = await conn.execute(text("SELECT id, name, slug FROM categories ORDER BY slug"))
        for c in result.fetchall():
            print(f"  {c.slug} ({c.name}) - {c.id}")
        
        # Brands
        print()
        print("Brands:")
        result = await conn.execute(text("SELECT id, name, slug FROM brands ORDER BY slug"))
        for b in result.fetchall():
            print(f"  {b.slug} ({b.name}) - {b.id}")

asyncio.run(check_products())