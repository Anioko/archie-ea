"""Synthetic vendor seed stub for the open-source build.

The production build ships a curated vendor dataset; this open-source stub
returns a small, fictional sample so the import resolves and the
populate-vendors feature runs against demo data instead of real records.
"""

def get_vendor_data():
    return [
        {"name": "Acme Cloud", "vendor_type": "cloud", "products": [
            {"name": "Acme Compute", "product_type": "platform"},
        ]},
        {"name": "Globex Software", "vendor_type": "software", "products": [
            {"name": "Globex ERP", "product_type": "application"},
        ]},
    ]
