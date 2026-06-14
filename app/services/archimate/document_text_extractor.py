"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.document_text_extractor
Backward-compat re-export. Canonical: app/modules/architecture/services/document_text_extractor.py
"""
from app.modules.architecture.services.document_text_extractor import (  # noqa: F401
    extract_text_from_file,
    extract_from_spreadsheet,
    extract_from_csv,
    extract_from_excel,
    extract_from_excel_legacy,
    extract_from_text_file,
    extract_from_pdf,
    extract_from_docx,
    extract_from_doc,
    extract_from_pptx,
    get_document_summary,
    parse_spreadsheet_to_records,
)
