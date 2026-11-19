"""Industry presets for terminology, modules, categories, and payment methods."""

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "Retail Shop": {"terminology": {"item": "Product", "customer": "Customer", "sale": "Sale"},
                    "categories": ["General", "Electronics", "Accessories"], "modules": {"barcode": True}},
    "Supermarket": {"terminology": {"item": "Product", "customer": "Customer", "sale": "Sale"},
                    "categories": ["Groceries", "Household", "Fresh Food"], "modules": {"barcode": True, "weighed_items": True}},
    "Pharmacy": {"terminology": {"item": "Medicine", "customer": "Customer", "sale": "Sale"},
                 "categories": ["Prescription", "Over the Counter"], "modules": {"barcode": True, "expiry_batches": True}},
    "Hardware": {"terminology": {"item": "Product", "customer": "Customer", "sale": "Sale"},
                 "categories": ["Tools", "Building Materials", "Electrical"], "modules": {"barcode": True, "serial_numbers": True}},
    "Fashion Boutique": {"terminology": {"item": "Product", "customer": "Customer", "sale": "Sale"},
                         "categories": ["Clothing", "Shoes", "Accessories"], "modules": {"variants": True}},
    "Café / Restaurant": {"terminology": {"item": "Menu item", "customer": "Guest", "sale": "Order"},
                          "categories": ["Food", "Drinks"], "modules": {"tables_order_types": True}},
    "Salon / Barber": {"terminology": {"item": "Service", "customer": "Client", "sale": "Appointment"},
                       "categories": ["Hair", "Nails", "Treatments"], "modules": {"services_appointments": True}},
    "Auto Garage": {"terminology": {"item": "Part or service", "customer": "Customer", "sale": "Job"},
                    "categories": ["Parts", "Labor"], "modules": {"serial_numbers": True}},
    "Wholesale": {"terminology": {"item": "Product", "customer": "Account", "sale": "Order"},
                  "categories": ["General", "Bulk"], "modules": {"price_tiers": True}},
    "Service Business": {"terminology": {"item": "Service", "customer": "Client", "sale": "Sale"},
                         "categories": ["Services"], "modules": {"services_appointments": True}},
    "Custom": {"terminology": {"item": "Item", "customer": "Customer", "sale": "Sale"},
               "categories": ["General"], "modules": {}},
}

MODULE_KEYS = (
    "barcode", "weighed_items", "variants", "expiry_batches", "tables_order_types",
    "services_appointments", "serial_numbers", "price_tiers", "loyalty", "multi_branch",
)
