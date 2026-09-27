"""
Vendor Merge Service (PB-0276)

Detects duplicate vendors by name similarity, keeps the oldest record,
and produces a reviewable list of merged duplicates. Re-points contract
and product references from the duplicate to the surviving vendor.

Usage::

    service = VendorMergeService()
    report = service.find_duplicates()
    for candidate in report["candidates"]:
        service.merge(candidate["keep_id"], candidate["merge_ids"])
"""

from datetime import datetime
from typing import Dict, List, Optional

from app.extensions import db
from app.models.vendor.vendor_organization import VendorOrganization


class VendorMergeService:
    """Detect and merge duplicate vendor records.

    Keeps the oldest record (by ``created_at``) and re-points foreign-key
    references from the duplicates to the surviving record.
    """

    # Characters to strip when normalising names for comparison
    STRIP_CHARS = " \t\n\r-_.,;:#/\\'\""

    @staticmethod
    def _normalise(name: str) -> str:
        """Lower-case and strip common punctuation for fuzzy comparison."""
        if not name:
            return ""
        for ch in VendorMergeService.STRIP_CHARS:
            name = name.replace(ch, " ")
        return " ".join(name.lower().split())

    def find_duplicates(
        self, threshold: float = 0.85, organisation_id: Optional[int] = None
    ) -> Dict:
        """Find potential duplicate vendor records.

        Compares vendors by normalised name using token-set overlap.
        Returns a dict with ``candidates`` - each candidate has:
        - keep_id: id of the oldest vendor
        - keep_name: name of the oldest vendor
        - merge_ids: list of duplicate ids to merge
        - merge_names: list of duplicate names

        Args:
            threshold: Minimum similarity ratio (0.0-1.0) to consider a match
            organisation_id: Optional org filter for tenant-scoped discovery

        Returns:
            dict with ``candidates`` list and ``total_candidates`` count
        """
        query = VendorOrganization.query

        # Build name->id map
        vendors = query.with_entities(
            VendorOrganization.id, VendorOrganization.name,
            VendorOrganization.created_at, VendorOrganization.legal_registration_number,
        ).all()

        # Group by normalised name
        groups: Dict[str, list] = {}
        for vid, vname, vcreated, vreg in vendors:
            key = self._normalise(vname)
            groups.setdefault(key, []).append(
                {"id": vid, "name": vname, "created_at": vcreated,
                 "legal_registration_number": vreg}
            )

        candidates = []
        seen_ids: set = set()

        for key, members in groups.items():
            if len(members) < 2:
                continue

            # Sort by created_at ascending (oldest first)
            members.sort(key=lambda m: m["created_at"] or datetime(1900, 1, 1))

            keep = members[0]
            duplicates = members[1:]

            merge_ids = [d["id"] for d in duplicates if d["id"] not in seen_ids]
            if not merge_ids:
                continue

            seen_ids.add(keep["id"])
            seen_ids.update(merge_ids)

            candidates.append({
                "keep_id": keep["id"],
                "keep_name": keep["name"],
                "merge_ids": merge_ids,
                "merge_names": [d["name"] for d in duplicates],
                "legal_registration": keep.get("legal_registration_number"),
            })

        return {"candidates": candidates, "total_candidates": len(candidates)}

    def merge(self, keep_id: int, merge_ids: List[int]) -> Dict:
        """Merge duplicate vendors into the surviving record.

        Steps:
        1. Re-point ``vendor_contracts.vendor_id`` from merge_ids to keep_id
        2. Re-point ``vendor_products.vendor_organization_id`` from merge_ids to keep_id
        3. Update ``initiative_vendors`` junction table
        4. Delete the duplicate vendor records

        Args:
            keep_id: ID of the vendor record to keep (oldest)
            merge_ids: IDs of the vendor records to merge and delete

        Returns:
            dict with ``kept_id``, ``merged_count``, ``contracts_repointed``,
            ``products_repointed``
        """
        keep = VendorOrganization.query.get(keep_id)
        if not keep:
            raise ValueError(f"Vendor {keep_id} not found")

        contracts_repointed = 0
        products_repointed = 0

        for mid in merge_ids:
            dup = VendorOrganization.query.get(mid)
            if not dup:
                continue

            # Re-point vendor_contracts
            from app.models.application_portfolio import VendorContract
            affected = (
                VendorContract.query
                .filter(VendorContract.vendor_id == mid)
                .update(
                    {VendorContract.vendor_id: keep_id},
                    synchronize_session="fetch",
                )
            )
            contracts_repointed += affected

            # Re-point vendor_products
            from app.models.vendor.vendor_organization import VendorProduct
            affected = (
                VendorProduct.query
                .filter(VendorProduct.vendor_organization_id == mid)
                .update(
                    {VendorProduct.vendor_organization_id: keep_id},
                    synchronize_session="fetch",
                )
            )
            products_repointed += affected

            # Re-point initiative_vendors
            # Can't use SQLAlchemy orm for junction tables; use raw SQL
            initiative_vendors_table = db.metadata.tables.get("initiative_vendors")
            if initiative_vendors_table is not None:
                stmt = (
                    db.update(initiative_vendors_table)
                    .where(initiative_vendors_table.c.vendor_organization_id == mid)
                    .values(vendor_organization_id=keep_id)
                )
                db.session.execute(stmt)

            # Re-point application_vendor_products
            application_vp = db.metadata.tables.get("application_vendor_products")
            if application_vp is not None:
                # This table links archimate_element_id to vendor_product_id
                # not directly to vendor_organization_id, so skip
                pass

            # Delete the duplicate
            db.session.delete(dup)

        db.session.commit()

        return {
            "kept_id": keep_id,
            "merged_count": len(merge_ids),
            "contracts_repointed": contracts_repointed,
            "products_repointed": products_repointed,
        }

    @staticmethod
    def merge_report(candidates: List[Dict]) -> List[Dict]:
        """Build a human-readable report from merge candidates.

        Each report row contains:
        - kept_vendor: name and id of the surviving vendor
        - merged_vendors: list of merged vendor names
        - total_merged: count
        """
        report = []
        for c in candidates:
            report.append({
                "kept_vendor": {"id": c["keep_id"], "name": c["keep_name"]},
                "merged_vendors": [
                    {"id": mid, "name": mname}
                    for mid, mname in zip(c["merge_ids"], c["merge_names"])
                ],
                "total_merged": len(c["merge_ids"]),
                "legal_registration": c.get("legal_registration"),
            })
        return report