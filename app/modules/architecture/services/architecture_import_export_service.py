"""
-> app.modules.architecture.services.governance_service

rchitecture import/export service."""

import logging
import csv
import io
import json
import os
import tempfile
from datetime import datetime
from typing import Dict, Tuple

from app.extensions import db
from app.models.archimate_core import ArchiMateElement as ArchitectureElement, ArchiMateRelationship as Relationship

logger = logging.getLogger(__name__)


class ArchitectureImportExportService:
    """Import and export architecture data."""
    
    @staticmethod
    def export_to_csv() -> Tuple[str, str]:
        """Export all architecture to CSV.
        
        Returns: (file_path, filename)
        """
        filename = f"architecture_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Create in-memory CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id", "name", "element_type", "layer", "description", "created_at"
            ]
        )
        
        writer.writeheader()
        
        elements = ArchitectureElement.query.all()
        for element in elements:
            writer.writerow({
                "id": element.id,
                "name": element.name,
                "element_type": element.element_type,
                "layer": element.layer,
                "description": element.description,
                "created_at": element.created_at.isoformat() if element.created_at else "",
            })
        
        # Save to temp file (use tempfile for cross-platform compatibility)
        tmp_fd, temp_path = tempfile.mkstemp(suffix=".csv", prefix="arch_export_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(output.getvalue())
        except Exception:
            # Ensure temp file is cleaned up if write fails
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return temp_path, filename
    
    @staticmethod
    def export_to_json() -> Tuple[str, str]:
        """Export all architecture to JSON.
        
        Returns: (file_path, filename)
        """
        filename = f"architecture_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        elements = ArchitectureElement.query.all()
        relationships = Relationship.query.all()
        
        data = {
            "elements": [e.to_dict() for e in elements],
            "relationships": [r.to_dict() for r in relationships],
            "exported_at": datetime.now().isoformat(),
        }
        
        # Save to temp file (use tempfile for cross-platform compatibility)
        tmp_fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="arch_export_")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Ensure temp file is cleaned up if write fails
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return temp_path, filename
    
    @staticmethod
    def import_from_csv(file) -> Dict:
        """Import architecture from CSV file.
        
        Returns: {imported: count, skipped: count, errors: []}
        """
        imported = 0
        skipped = 0
        errors = []
        
        try:
            stream = io.TextIOWrapper(file.stream, encoding="utf-8")
            reader = csv.DictReader(stream)

            # Batch-load existing element names to avoid N+1 queries in the loop
            existing_names = {
                e.name for e in ArchitectureElement.query.with_entities(ArchitectureElement.name).all()
            }

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Check if element exists using pre-loaded set
                    if row["name"] in existing_names:
                        skipped += 1
                        continue

                    # Create element
                    element = ArchitectureElement(
                        name=row["name"],
                        element_type=row["element_type"],
                        layer=row.get("layer"),
                        description=row.get("description"),
                    )

                    db.session.add(element)
                    # Track newly added names to avoid duplicates within the same import
                    existing_names.add(row["name"])
                    imported += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    skipped += 1

            db.session.commit()
            
        except Exception as e:
            errors.append(f"Import failed: {str(e)}")
        
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }
    
    @staticmethod
    def import_from_json(file) -> Dict:
        """Import architecture from JSON file.
        
        Returns: {imported: count, skipped: count, errors: []}
        """
        imported = 0
        skipped = 0
        errors = []
        
        try:
            data = json.load(file)

            # Batch-load existing element names to avoid N+1 queries in the loop
            existing_names = {
                e.name for e in ArchitectureElement.query.with_entities(ArchitectureElement.name).all()
            }

            # Import elements
            for element_data in data.get("elements", []):
                try:
                    # Check if element exists using pre-loaded set
                    if element_data["name"] in existing_names:
                        skipped += 1
                        continue

                    element = ArchitectureElement(
                        name=element_data["name"],
                        element_type=element_data["element_type"],
                        layer=element_data.get("layer"),
                        description=element_data.get("description"),
                    )

                    db.session.add(element)
                    # Track newly added names to avoid duplicates within the same import
                    existing_names.add(element_data["name"])
                    imported += 1

                except Exception as e:
                    errors.append(f"Element import: {str(e)}")
                    skipped += 1

            db.session.commit()
            
        except Exception as e:
            errors.append(f"JSON import failed: {str(e)}")
        
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }
    
    @staticmethod
    def export_data(format_type: str = "csv") -> Tuple[str, str]:
        """Export in specified format.
        
        Returns: (file_path, filename)
        """
        if format_type == "json":
            return ArchitectureImportExportService.export_to_json()
        else:
            return ArchitectureImportExportService.export_to_csv()
    
    @staticmethod
    def import_data(file, format_type: str = "csv") -> Dict:
        """Import from specified format.
        
        Returns: {imported, skipped, errors}
        """
        if format_type == "json":
            return ArchitectureImportExportService.import_from_json(file)
        else:
            return ArchitectureImportExportService.import_from_csv(file)
