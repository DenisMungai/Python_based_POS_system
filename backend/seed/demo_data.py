"""Reproducible sample catalogue data for local demonstration and smoke checks."""

from backend.services.catalog import CatalogService


def seed_retail(catalog: CatalogService) -> tuple[int, ...]:
    """Create sample retail items, with Laptop fixed at item ID 101."""
    if catalog.repo.find("items", limit=1):
        return tuple(int(item["id"]) for item in catalog.repo.find("items", order_by="id"))
    category = catalog.repo.find("categories", {"name": "Electronics"}, limit=1)
    category_id = int(category[0]["id"]) if category else catalog.create_category("Electronics")
    laptop_id = catalog.create_item(
        "Laptop", 85_000_000, cost_minor=70_000_000, stock_milli=10_000,
        low_stock_milli=2_000, category_id=category_id,
    )
    catalog.create_item("Wireless Mouse", 180_000, cost_minor=90_000, stock_milli=24_000,
                        category_id=category_id)
    catalog.create_item("USB-C Hub", 450_000, cost_minor=300_000, stock_milli=8_000,
                        category_id=category_id)
    return (laptop_id, *(int(item["id"]) for item in catalog.repo.find("items", order_by="id") if item["id"] != laptop_id))


def seed_business(catalog: CatalogService, business_type: str) -> tuple[int, ...]:
    """Create sample data appropriate to the selected business preset."""
    if business_type == "Salon / Barber":
        category = catalog.repo.find("categories", {"name": "Hair"}, limit=1)
        category_id = int(category[0]["id"]) if category else catalog.create_category("Hair")
        return (
            catalog.create_item("Haircut", 150_000, item_type="service", category_id=category_id),
            catalog.create_item("Wash and style", 250_000, item_type="service", category_id=category_id),
        )
    if business_type == "Café / Restaurant":
        category = catalog.repo.find("categories", {"name": "Food"}, limit=1)
        category_id = int(category[0]["id"]) if category else catalog.create_category("Food")
        return (
            catalog.create_item("Coffee", 35_000, stock_milli=100_000, category_id=category_id),
            catalog.create_item("Sandwich", 65_000, stock_milli=30_000, category_id=category_id),
        )
    return seed_retail(catalog)
