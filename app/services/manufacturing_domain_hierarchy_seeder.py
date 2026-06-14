"""
Manufacturing Domain Hierarchy Seeding Service

Manages creation and updates of manufacturing domain hierarchy.
Two-pass approach: creates domains first, then sets parent relationships.
"""

from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ManufacturingDomainHierarchy

from app.seed_data.manufacturing_domain_hierarchy_seed_data import MANUFACTURING_DOMAIN_HIERARCHY


class ManufacturingDomainHierarchySeeder:
    """Seeds manufacturing domain hierarchy with proper parent-child relationships."""

    def __init__(self):
        self.created_count = 0
        self.updated_count = 0
        self.error_count = 0
        self.domain_map = {}  # code -> id mapping

    def seed(self) -> Dict:
        """
        Seed manufacturing domain hierarchy using two-pass approach.

        Returns:
            Dict with created, updated, error counts
        """
        try:
            # Pass 1: Create all domains without parent links
            self._pass_1_create_domains()

            # Pass 2: Set parent relationships
            self._pass_2_set_parents()

            return {
                "status": "success",
                "created": self.created_count,
                "updated": self.updated_count,
                "errors": self.error_count,
                "message": f"Created {self.created_count} domains, updated {self.updated_count}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "created": self.created_count,
                "updated": self.updated_count,
                "errors": self.error_count,
            }

    def _pass_1_create_domains(self):
        """Pass 1: Create all domain records without parent links (recursive)."""
        def create_recursive(items):
            for item_data in items:
                self._create_or_update_domain(item_data, parent_id=None)
                if "subdomains" in item_data:
                    create_recursive(item_data["subdomains"])

        create_recursive(MANUFACTURING_DOMAIN_HIERARCHY)

    def _pass_2_set_parents(self):
        """Pass 2: Set parent relationships using code mapping (recursive)."""
        # Batch prefetch all domain records by code to avoid N+1 queries in recursive loop
        all_domains = ManufacturingDomainHierarchy.query.all()
        domain_by_code = {d.code: d for d in all_domains if d.code}

        def set_parents_recursive(items):
            for item_data in items:
                if "subdomains" in item_data:
                    parent_code = item_data["code"]
                    parent_id = self.domain_map.get(parent_code)

                    if parent_id:
                        for subdomain_data in item_data["subdomains"]:
                            subdomain_code = subdomain_data["code"]
                            subdomain_record = domain_by_code.get(subdomain_code)

                            if subdomain_record and subdomain_record.parent_id != parent_id:
                                subdomain_record.parent_id = parent_id
                                self.updated_count += 1

                            if subdomain_record:
                                db.session.add(subdomain_record)

                    set_parents_recursive(item_data["subdomains"])

        set_parents_recursive(MANUFACTURING_DOMAIN_HIERARCHY)

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            self.error_count += 1
            print(f"Error setting parents: {e}")

    def _create_or_update_domain(
        self, domain_data: Dict, parent_id=None
    ) -> ManufacturingDomainHierarchy:
        """Create or update a single domain."""
        code = domain_data["code"]

        # Check if exists
        record = ManufacturingDomainHierarchy.query.filter_by(code=code).first()

        if not record:
            # Create new
            record = ManufacturingDomainHierarchy(
                code=code,
                name=domain_data["name"],
                description=domain_data.get("description"),
                level=domain_data.get("level", 1),
                sort_order=domain_data.get("sort_order", 0),
                domain_patterns=domain_data.get("domain_patterns"),
                parent_id=parent_id,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.created_count += 1
        else:
            # Update existing
            record.name = domain_data["name"]
            record.description = domain_data.get("description")
            record.level = domain_data.get("level", 1)
            record.sort_order = domain_data.get("sort_order", 0)
            record.domain_patterns = domain_data.get("domain_patterns")
            record.is_active = True
            record.updated_at = datetime.utcnow()
            self.updated_count += 1

        db.session.add(record)
        try:
            db.session.flush()
            self.domain_map[code] = record.id
        except IntegrityError as e:
            db.session.rollback()
            self.error_count += 1
            print(f"Error creating domain {code}: {e}")

        return record

    def get_domain_tree(self) -> List[Dict]:
        """Get hierarchical tree of all domains."""
        # Get all primary domains (level 1)
        primary_domains = (
            ManufacturingDomainHierarchy.query.filter_by(level=1)
            .order_by(ManufacturingDomainHierarchy.sort_order)
            .all()
        )

        tree = []
        for domain in primary_domains:
            domain_dict = {
                "id": domain.id,
                "code": domain.code,
                "name": domain.name,
                "description": domain.description,
                "level": domain.level,
                "domain_patterns": domain.domain_patterns,
                "subdomains": [],
            }

            # Get subdomains
            for subdomain in domain.subdomains:
                subdomain_dict = {
                    "id": subdomain.id,
                    "code": subdomain.code,
                    "name": subdomain.name,
                    "description": subdomain.description,
                    "level": subdomain.level,
                    "domain_patterns": subdomain.domain_patterns,
                }
                domain_dict["subdomains"].append(subdomain_dict)

            tree.append(domain_dict)

        return tree
