"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.unified_import_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/file_parser.py
"""

from app.modules.import_batch.services.file_parser import (  # noqa: F401
    FileParser,
    FileStats,
)
