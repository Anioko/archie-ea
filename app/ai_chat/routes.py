import asyncio  # dead-code-ok
import json
import logging
import os
import time  # dead-code-ok
from datetime import datetime  # dead-code-ok

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models.ai_service import AIPromptTemplate
from app.models.application_layer import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.unified_capability import UnifiedCapability
from app.models.vendor.vendor_organization import VendorOrganization

# Use shared event loop utility to prevent memory leaks
from app.services.core.async_utils import get_or_create_event_loop
from app.services.llm_service import LLMService
from app.services.multi_domain_chat_service import MultiDomainChatService

ai_chat = Blueprint("ai_chat", __name__, template_folder="../templates/ai_chat")

logger = logging.getLogger(__name__)


# Initialize multi-domain chat service
def get_chat_service():
    """Get multi-domain chat service instance"""
    try:
        user_id = None
        if (
            current_user
            and hasattr(current_user, "is_authenticated")
            and current_user.is_authenticated
        ):
            user_id = current_user.id
        return MultiDomainChatService(user_id=user_id)
    except Exception as e:
        current_app.logger.error(f"Error creating chat service: {e}")
        # Return a basic service instance for unauthenticated users
        return MultiDomainChatService(user_id=None)


@ai_chat.route("/")
@login_required
def index():
    """Renders the Enhanced Multi-Domain AI Chat Interface."""
    # Pre-fetch prompt templates for the UI selector
    templates = AIPromptTemplate.query.all()

    # Get multi-domain service and configurations
    chat_service = get_chat_service()
    domain_config = chat_service.get_available_domains()
    persona_config = chat_service.get_available_personas()

    # Get context data for different domains
    context_data = {
        "applications": ApplicationComponent.query.limit(10).all(),
        "capabilities": BusinessCapability.query.limit(10).all(),
        "vendors": VendorOrganization.query.limit(10).all(),
        "unified_capabilities": UnifiedCapability.query.limit(10).all(),
    }

    return render_template(
        "ai_chat/index.html",
        prompt_templates=templates,
        domain_config=domain_config,
        persona_config=persona_config,
        context_data=context_data,
    )


@ai_chat.route("/document-upload")
@login_required
def document_upload_view():
    """Renders the Document Upload interface for AI-powered document analysis."""
    return render_template("ai_chat/document_upload.html")


@ai_chat.route("/business-output")
@login_required
def business_output_view():
    """Renders the Business Output interface for AI-generated insights."""
    return render_template("ai_chat/business_output.html")


@ai_chat.route("/entity-matching")
@login_required
def entity_matching_view():
    """Renders the Entity Matching interface for AI-powered entity resolution."""
    return render_template("ai_chat/entity_matching_chat_interface.html")


@ai_chat.route("/message", methods=["POST"])
@login_required
def send_message():
    """Handles multi-domain chat messages."""
    # Check if user is authenticated
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required to send messages"}), 401

    data = request.json
    user_message = data.get("message")
    domain = data.get("domain", "general")
    template_name = data.get("template_name", "General Inquiry")
    context_element_id = data.get("element_id")
    context_type = data.get("context_type")
    persona = data.get("persona")  # Extract persona from request

    if not user_message:
        return jsonify({"error": "Message content is required"}), 400

    try:
        # Get multi-domain chat service
        chat_service = get_chat_service()

        # Prepare context data
        context_data = {}
        if context_element_id and context_type:
            context_data = {
                "element_id": context_element_id,
                "context_type": context_type,
                "domain": domain,
            }

        # Add document context from uploaded documents
        from app.models.ai_chat_document import AIChatDocumentUpload

        # Get recent completed document uploads for this user
        recent_docs = (
            AIChatDocumentUpload.query.filter_by(uploaded_by_id=current_user.id, status="completed")
            .order_by(AIChatDocumentUpload.analyzed_at.desc())
            .limit(5)
            .all()
        )

        document_context = []
        for doc in recent_docs:
            if doc.analysis_results:
                try:
                    analysis = (
                        json.loads(doc.analysis_results)
                        if isinstance(doc.analysis_results, str)
                        else doc.analysis_results
                    )
                    document_context.append(
                        {
                            "filename": doc.original_filename,
                            "uploaded_at": doc.analyzed_at.isoformat() if doc.analyzed_at else None,
                            "elements_found": len(analysis.get("elements", [])),
                            "elements_created": doc.created_elements_count or 0,
                            "summary": doc.chat_context_summary or "",
                            "elements": analysis.get("elements", [])[
                                :10
                            ],  # Limit to first 10 elements
                            "relationships": analysis.get("relationships", [])[
                                :10
                            ],  # Limit to first 10 relationships
                        }
                    )
                except (json.JSONDecodeError, TypeError):
                    # Skip malformed JSON
                    continue

        if document_context:
            context_data["uploaded_documents"] = document_context

        # Process message using multi-domain service with persona support
        response_data = chat_service.process_message(
            message=user_message,
            domain=domain,
            template=template_name,
            context=context_data,
            persona=persona,  # Pass persona to service for personalized responses
        )

        return jsonify(
            {
                "response": response_data.get(
                    "response", "I processed your request but found no specific output."
                ),
                "data": response_data,
                "domain": domain,
                "persona": persona,  # Include persona in response
                "metadata": response_data.get("metadata", {}),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Chat Error in {domain} domain: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@ai_chat.route("/domains")
@login_required
def get_domains():
    """Get available chat domains."""
    # Check if user is authenticated
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required to access domains"}), 401

    chat_service = get_chat_service()
    domain_info = chat_service.get_available_domains()
    return jsonify(domain_info)


@ai_chat.route("/context/<domain>")
@login_required
def get_domain_context(domain):
    """Get context data for specific domain."""
    # Check if user is authenticated
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required to access context"}), 401

    try:
        chat_service = get_chat_service()
        context_data = chat_service.get_domain_context(domain)
        return jsonify(context_data)

    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@ai_chat.route("/personas")
@login_required
def get_personas():
    """Get available personas with their configurations."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required to access personas"}), 401

    try:
        chat_service = get_chat_service()
        persona_info = chat_service.get_available_personas()
        return jsonify(persona_info)

    except Exception as e:
        current_app.logger.error(f"Error getting personas: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@ai_chat.route("/persona-context/<persona>")
@login_required
def get_persona_context(persona):
    """Get context data specific to a persona."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required to access persona context"}), 401

    try:
        chat_service = get_chat_service()
        context_data = chat_service.get_persona_context(persona, limit=20)
        return jsonify(context_data)

    except Exception as e:
        current_app.logger.error(f"Error getting persona context: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


# =============================================================================
# Natural Language Query Routes
# =============================================================================


@ai_chat.route("/nl-query", methods=["POST"])
@login_required
def natural_language_query():
    """
    Process a natural language query against the database.

    Expected JSON body:
    {
        "query": "Show me all applications without business owner",
        "persona": "enterprise_architect" (optional)
    }
    """
    try:
        from app.services.natural_language_query_service import NaturalLanguageQueryService

        data = request.get_json()
        if not data or not data.get("query"):
            return jsonify({"error": "Query is required"}), 400

        query = data.get("query")
        persona = data.get("persona")

        nl_service = NaturalLanguageQueryService()
        result = nl_service.process_query(query, persona)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Error processing NL query: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "suggestions": [
                        "Try: 'Show all applications without business owner'",
                        "Try: 'List capabilities with maturity below 3'",
                        "Try: 'Which vendors expire in 90 days?'",
                    ],
                }
            ),
            500,
        )


@ai_chat.route("/nl-query/examples")
@login_required
def get_query_examples():
    """Get example queries for the NL Query interface."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    try:
        from app.services.natural_language_query_service import NaturalLanguageQueryService

        nl_service = NaturalLanguageQueryService()
        examples = nl_service.get_supported_queries()
        return jsonify(examples)

    except Exception as e:
        current_app.logger.error(f"Error getting query examples: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


# =============================================================================
# Recommendations Engine Routes
# =============================================================================


@ai_chat.route("/recommendations")
@login_required
def get_recommendations():
    """
    Get actionable recommendations and alerts.

    Query params:
    - persona: Filter by persona (optional)
    - refresh: Force refresh cache (optional)
    """
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        persona = request.args.get("persona")
        refresh = request.args.get("refresh", "false").lower() == "true"

        rec_service = RecommendationsEngineService()
        recommendations = rec_service.get_all_recommendations(persona=persona, refresh=refresh)

        return jsonify(recommendations)

    except Exception as e:
        current_app.logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return (
            jsonify(
                {"error": str(e), "alerts": [], "recommendations": [], "summary": {"total": 0}}
            ),
            500,
        )


@ai_chat.route("/recommendations/quick-stats")
@login_required
def get_quick_stats():
    """Get quick statistics for dashboard display."""
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        rec_service = RecommendationsEngineService()
        stats = rec_service.get_quick_stats()

        return jsonify(stats)

    except Exception as e:
        current_app.logger.error(f"Error getting quick stats: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@ai_chat.route("/recommendations/alerts")
@login_required
def get_alerts_only():
    """Get only alerts (for notification badges, etc.)."""
    try:
        from app.services.recommendations_engine_service import RecommendationsEngineService

        persona = request.args.get("persona")
        rec_service = RecommendationsEngineService()
        data = rec_service.get_all_recommendations(persona=persona)

        # Return only alerts with summary
        return jsonify(
            {
                "alerts": data.get("alerts", []),
                "summary": data.get("summary", {}),
                "health_score": data.get("health_score", 0),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting alerts: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred", "alerts": []}), 500


# =============================================================================
# Document Upload and Auto-Creation Routes
# =============================================================================


@ai_chat.route("/upload-document", methods=["POST"])
@login_required
def upload_document():
    """
    Upload document and automatically create ArchiMate elements in Architecture CRUD.

    Extracts elements from uploaded documents and creates them in the appropriate tables.
    Supports context-aware analysis for applications and vendors.
    """
    try:
        from werkzeug.utils import secure_filename

        from app.archimate_crud.routes import LAYER_CONFIG, MODEL_REGISTRY
        from app.services.archimate.document_analysis_service import DocumentAnalysisService

        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Get user ID
        user_id = current_user.id if current_user.is_authenticated else None

        # Get context-aware parameters
        analysis_context = request.form.get(
            "analysis_context", "general"
        )  # 'general', 'application', or 'vendor'
        target_application_id = request.form.get("target_application_id")
        target_vendor_id = request.form.get("target_vendor_id")

        # Convert IDs to integers if provided
        if target_application_id:
            try:
                target_application_id = int(target_application_id)
            except ValueError:
                target_application_id = None

        if target_vendor_id:
            try:
                target_vendor_id = int(target_vendor_id)
            except ValueError:
                target_vendor_id = None

        # Check if this is preview-only mode (extract but don't create)
        preview_only = request.form.get("preview_only", "false").lower() == "true"

        current_app.logger.info(
            f"Document upload - Context: {analysis_context}, App ID: {target_application_id}, Vendor ID: {target_vendor_id}, Preview: {preview_only}"
        )

        # Create document upload record
        from app.models.ai_chat_document import AIChatDocumentUpload

        original_filename = file.filename
        file_size = len(file.read())
        file.seek(0)  # Reset file pointer

        # File size validation (max 50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes
        if file_size > MAX_FILE_SIZE:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum allowed size (50MB)",
                    }
                ),
                400,
            )

        # File type validation
        ALLOWED_EXTENSIONS = {
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".pptx",
            ".ppt",
            ".csv",
            ".xlsx",
            ".xls",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
        }
        file_ext = os.path.splitext(original_filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"File type '{file_ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                    }
                ),
                400,
            )

        # MIME type validation for additional security
        ALLOWED_MIME_TYPES = {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
            "text/plain",
            "text/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "image/png",
            "image/jpeg",
            "image/gif",
        }
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            current_app.logger.warning(
                f"Suspicious MIME type: {file.content_type} for file {original_filename}"
            )

        # Save uploaded file
        upload_folder = os.path.join(current_app.root_path, "uploads", "ai_chat", "documents")
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # Determine file type
        file_ext = os.path.splitext(filename)[1].lower()
        file_type_map = {
            ".pdf": "document",
            ".doc": "document",
            ".docx": "document",
            ".txt": "document",
            ".pptx": "document",
            ".ppt": "document",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".gif": "image",
            ".xlsx": "spreadsheet",
            ".xls": "spreadsheet",
            ".csv": "spreadsheet",
        }
        file_type = file_type_map.get(file_ext, "document")

        # Create upload record with retry logic for CockroachDB
        from app.services.core.retry_handler import execute_with_db_retry

        upload_record = None

        def create_upload_record():
            nonlocal upload_record
            upload_record = AIChatDocumentUpload(
                file_name=unique_filename,
                original_filename=original_filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                mime_type=file.content_type,
                status="uploading",
                uploaded_by_id=user_id,
                provider=request.form.get("provider", "claude"),
            )
            db.session.add(upload_record)
            db.session.flush()
            return upload_record

        success, _, error = execute_with_db_retry(
            create_upload_record, operation_name="create upload record"
        )

        if not success or not upload_record:
            raise Exception(f"Failed to create upload record: {error}")

        # Update status to analyzing with retry logic
        def update_status():
            db.session.refresh(upload_record)
            upload_record.status = "analyzing"
            upload_record.upload_progress = 50
            db.session.commit()

        success, _, error = execute_with_db_retry(
            update_status, operation_name="update status to analyzing"
        )

        if not success:
            current_app.logger.warning(
                f"Could not update status to analyzing after retries: {error}"
            )
            # Continue with analysis even if status update fails

        # Analyze document
        analysis_service = DocumentAnalysisService()

        # Get or create event loop for async operations
        loop = get_or_create_event_loop()

        # Get provider from request (default to claude, but check for gemini preference)
        provider = request.form.get("provider", "claude")

        # Map UI provider names to database provider names
        if provider == "claude":
            provider = "anthropic"

        # For PDFs, prefer Gemini if available (better native PDF support)
        if file_type == "document" and file_path.lower().endswith(".pdf"):
            # Check if Gemini is configured
            from app.models.models import APISettings

            gemini_settings = APISettings.query.filter_by(provider="gemini", enabled=True).first()
            if gemini_settings and gemini_settings.api_key:
                provider = "gemini"
                current_app.logger.info("Using Gemini for native PDF processing")

        # Determine analysis context for intelligent element extraction
        # Map analysis_context to appropriate extraction focus ('application', 'vendor', or 'architecture')
        if analysis_context == "application":
            extraction_context = "application"
        elif analysis_context == "vendor":
            extraction_context = "vendor"
        else:
            extraction_context = "architecture"

        current_app.logger.info(f"Using extraction context: {extraction_context}")

        # Analyze document with context-aware analysis
        # The DocumentAnalysisService handles context-specific prompts internally
        if file_type == "image":
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_image(file_path, provider, extraction_context)
            )
        elif file_type == "document":
            extracted_data, interactions = loop.run_until_complete(
                analysis_service._analyze_document(file_path, provider, extraction_context)
            )
            interaction = interactions[0] if interactions else None
        elif file_type == "spreadsheet":
            extracted_data, interaction = analysis_service._analyze_spreadsheet(
                file_path, provider, analysis_type=extraction_context
            )
        else:
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_text_file(file_path, provider, extraction_context)
            )

        # Log extracted data for debugging
        current_app.logger.info(f"Document analysis result keys: {list(extracted_data.keys())}")
        current_app.logger.info(f"Extracted data metadata: {extracted_data.get('metadata', {})}")

        # Extract ArchiMate elements
        archimate_elements = extracted_data.get("elements", [])
        relationships = extracted_data.get("relationships", [])

        # Log what was extracted
        current_app.logger.info(
            f"Found {len(archimate_elements)} elements and {len(relationships)} relationships"
        )
        if archimate_elements:
            current_app.logger.info(
                f"Sample elements: {[e.get('name', 'Unknown') for e in archimate_elements[:3]]}"
            )
        else:
            # Check if there's an error in metadata
            metadata = extracted_data.get("metadata", {})
            if "error" in metadata:
                current_app.logger.error(f"Document analysis error: {metadata.get('error')}")
                if "raw_response" in metadata:
                    raw_resp = metadata.get("raw_response", "")
                    current_app.logger.error(
                        f"Raw LLM response (first 1000 chars): {raw_resp[:1000]}"
                    )
                    current_app.logger.error(
                        f"Raw LLM response (last 1000 chars): {raw_resp[-1000:] if len(raw_resp) > 1000 else raw_resp}"
                    )

            # If no elements found and no clear error, try a more aggressive extraction
            if len(archimate_elements) == 0 and not metadata.get("error"):
                current_app.logger.warning(
                    "No elements extracted, attempting retry with more explicit prompt"
                )
                try:
                    # Retry with a simpler, more direct prompt
                    retry_prompt = f"""
You are an ArchiMate 3.2 expert. Analyze this document and extract ALL architecture elements you can identify.

Return ONLY valid JSON in this format:
{{
  "elements": [
    {{"name": "Element Name", "type": "ElementType", "layer": "layer", "description": "Description"}}
  ],
  "relationships": [],
  "metadata": {{"confidence": "medium"}}
}}

Extract ANY elements you see: applications, systems, processes, actors, services, interfaces, data objects, etc.
Be liberal - if you see something that could be an ArchiMate element, include it.

Return ONLY JSON, no other text.
"""

                    # Use text extraction for retry
                    from app.services.archimate.document_text_extractor import (
                        extract_text_from_file,
                    )

                    text_content = extract_text_from_file(file_path, file_type)
                    if text_content and not text_content.startswith("Error"):
                        retry_prompt = retry_prompt + f"\n\nDocument text:\n{text_content[:10000]}"

                        provider_name, model = LLMService._get_configured_provider()
                        retry_response, retry_interaction = LLMService._call_llm(
                            prompt=retry_prompt,
                            model=model,
                            provider=provider_name,
                            user_id=None,
                            project_id=None,
                            max_tokens=8000,
                        )

                        current_app.logger.info(
                            f"Retry response length: {len(retry_response)} chars"
                        )
                        retry_data = analysis_service._parse_llm_response(retry_response)
                        retry_elements = retry_data.get("elements", [])

                        if retry_elements:
                            current_app.logger.info(
                                f"Retry successful: found {len(retry_elements)} elements"
                            )
                            archimate_elements = retry_elements
                            relationships = retry_data.get("relationships", [])
                            # Merge metadata
                            extracted_data["elements"] = archimate_elements
                            extracted_data["relationships"] = relationships
                            extracted_data["metadata"] = retry_data.get("metadata", {})
                            extracted_data["metadata"]["retry_used"] = True
                        else:
                            current_app.logger.warning("Retry also found 0 elements")
                except Exception as retry_error:
                    current_app.logger.error(f"Retry failed: {retry_error}", exc_info=True)

        # PREVIEW MODE: Return extracted elements without creating them
        if preview_only:
            current_app.logger.info(
                f"Preview mode: returning {len(archimate_elements)} extracted elements without creating"
            )

            # Check if Simple Parsing fallback was used
            metadata = extracted_data.get("metadata", {})
            fallback_used = metadata.get("parsing_method") == "simple_parser_fallback"
            fallback_message = None

            if fallback_used:
                fallback_message = {
                    "type": "info",
                    "title": "💰 LLM Budget Exhausted - Free Parsing Used",
                    "message": metadata.get(
                        "user_message",
                        "LLM budget exhausted. Used free Simple Parsing instead (CSV/Excel only).",
                    ),
                    "details": "Your document was parsed using pattern matching instead of AI. This works great for structured files like CSV/Excel!",
                }

            # If no elements found, provide helpful error message
            if len(archimate_elements) == 0:
                error_message = extracted_data.get("metadata", {}).get(
                    "error", "No ArchiMate elements could be identified in the document."
                )
                current_app.logger.warning(f"Preview mode: No elements extracted - {error_message}")
                return jsonify(
                    {
                        "success": True,
                        "message": "Document analyzed but no elements found",
                        "preview_mode": True,
                        "extracted_elements": [],
                        "relationships": [],
                        "metadata": {
                            **extracted_data.get("metadata", {}),
                            "error": error_message,
                            "suggestion": "Try uploading a document with application names, system descriptions, or architecture diagrams.",
                        },
                        "file_name": filename,
                        "upload_id": upload_record.id if upload_record else None,
                        "preview_analysis": {
                            "total_elements": 0,
                            "elements_with_missing_fields": 0,
                            "elements_with_duplicates": 0,
                            "average_completeness_score": 0,
                            "elements_with_generated_suggestions": 0,
                        },
                    }
                )

            # ENHANCED: Analyze missing fields and generate suggestions
            from app.services.archimate.missing_fields_analyzer import MissingFieldsAnalyzer

            analyzer = MissingFieldsAnalyzer()

            # Analyze missing fields for each element
            analyzed_elements = []
            for elem in archimate_elements:
                # Analyze missing fields
                analyzed = analyzer.analyze_missing_fields(
                    [elem], elem.get("type", "ApplicationComponent")
                )
                if analyzed:
                    analyzed_elem = analyzed[0]

                    # Generate missing fields if important fields are missing
                    missing_important = analyzed_elem.get("missing_fields", {}).get("important", [])
                    if missing_important:
                        generated = analyzer.generate_missing_fields(
                            analyzed_elem,
                            analyzed_elem.get("type", "ApplicationComponent"),
                            use_llm=True,
                        )
                        analyzed_elem["generated_fields"] = generated
                        analyzed_elem["has_generated_suggestions"] = True

                    # If element exists in DB, compare with existing
                    if analyzed_elem.get("properties", {}).get("exists_in_db"):
                        try:
                            from app.models.archimate_core import ArchiMateElement

                            existing_id = analyzed_elem["properties"].get("existing_element_id")
                            if existing_id:
                                existing_elem = ArchiMateElement.query.get(existing_id)
                                if existing_elem:
                                    # Try to get ApplicationComponent if linked
                                    if hasattr(existing_elem, "application_component"):
                                        app_component = existing_elem.application_component
                                        if app_component:
                                            comparison = analyzer.compare_with_existing(
                                                analyzed_elem, app_component
                                            )
                                            analyzed_elem["duplicate_comparison"] = comparison
                        except Exception as e:
                            current_app.logger.warning(
                                f"Error comparing with existing element: {e}"
                            )

                    analyzed_elements.append(analyzed_elem)
                else:
                    analyzed_elements.append(elem)

            # Calculate summary statistics
            total_elements = len(analyzed_elements)
            elements_with_missing = sum(
                1 for e in analyzed_elements if e.get("missing_fields", {}).get("all_missing")
            )
            elements_with_duplicates = sum(
                1 for e in analyzed_elements if e.get("properties", {}).get("exists_in_db")
            )
            avg_completeness = (
                sum(e.get("completeness_score", 0) for e in analyzed_elements) / total_elements
                if total_elements > 0
                else 0
            )

            # Save upload record in preview state
            try:
                upload_record.status = "preview"
                upload_record.upload_progress = 100
                db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Could not update upload record for preview: {e}")

            return jsonify(
                {
                    "success": True,
                    "message": f"Preview mode: Found {len(analyzed_elements)} elements",
                    "preview_mode": True,
                    "extracted_elements": analyzed_elements,
                    "relationships": relationships,
                    "metadata": extracted_data.get("metadata", {}),
                    "fallback_message": fallback_message,  # Include fallback notification
                    "file_name": filename,
                    "upload_id": upload_record.id if upload_record else None,
                    "preview_analysis": {
                        "total_elements": total_elements,
                        "elements_with_missing_fields": elements_with_missing,
                        "elements_with_duplicates": elements_with_duplicates,
                        "average_completeness_score": round(avg_completeness, 1),
                        "elements_with_generated_suggestions": sum(
                            1 for e in analyzed_elements if e.get("has_generated_suggestions")
                        ),
                    },
                }
            )

        # Auto-create elements in Architecture CRUD tables with proper transaction handling
        created_elements = []
        created_count = 0
        errors = []

        # Import ArchiMateElement at the top of the loop to avoid repeated imports
        # Import field mapper
        from app.ai_chat.element_field_mapper import (
            check_element_exists,
            map_element_data_to_model_fields,
        )
        from app.models.archimate_core import ArchiMateElement

        for elem in archimate_elements:
            element_type = elem.get("type")
            name = elem.get("name", "").strip()
            layer = elem.get("layer", "").lower()

            if not name:
                errors.append(f"Element with type '{element_type}' has no name - skipped")
                continue

            # Find the model class
            model_class = MODEL_REGISTRY.get(element_type)
            if not model_class:
                errors.append(f"Element type '{element_type}' not supported in Architecture CRUD")
                continue

            # Check if element already exists (using correct field name)
            existing = check_element_exists(model_class, element_type, name)
            if existing:
                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "status": "skipped",
                        "reason": "Already exists",
                    }
                )
                continue

            # Use savepoint for each element creation to prevent partial failures
            try:
                # Begin a savepoint for this element
                savepoint = db.session.begin_nested()

                # Map element data to model-specific fields
                element_data = map_element_data_to_model_fields(element_type, elem, user_id)

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = user_id

                # Create the element
                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()  # Get the ID

                # Auto-create ArchiMateElement link
                archimate_element = ArchiMateElement(
                    name=name,
                    type=element_type,
                    layer=layer if layer else None,
                    description=elem.get("description", ""),
                )
                db.session.add(archimate_element)
                db.session.flush()

                # Link them
                new_element.archimate_element_id = archimate_element.id

                # Link to target application or vendor if specified
                linked_to = None
                if target_application_id and analysis_context == "application":
                    # Link element to the target application
                    # For ApplicationComponent/Service/Interface, try to set parent relationship
                    if hasattr(new_element, "application_id"):  # model-safety-ok: dynamic model class
                        new_element.application_id = target_application_id
                        linked_to = {"type": "application", "id": target_application_id}
                    # Also add to relationship table if available
                    try:
                        from app.models.relationship_tables import application_component_elements

                        # Create association if table exists
                        if element_type in [
                            "ApplicationService",
                            "ApplicationInterface",
                            "DataObject",
                            "ApplicationFunction",
                        ]:
                            db.session.execute(  # tenant-filtered: scoped via parent FK
                                application_component_elements.insert().values(
                                    application_component_id=target_application_id,
                                    archimate_element_id=archimate_element.id,
                                )
                            )
                            linked_to = {"type": "application", "id": target_application_id}
                    except Exception as link_error:
                        current_app.logger.warning(
                            f"Could not link element to application: {link_error}"
                        )

                elif target_vendor_id and analysis_context == "vendor":
                    # Link element to the target vendor
                    if hasattr(new_element, "vendor_id"):  # model-safety-ok: dynamic model class
                        new_element.vendor_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    elif hasattr(new_element, "organization_id"):  # model-safety-ok: dynamic model class
                        new_element.organization_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    # For vendor products, try to create vendor product relationship
                    try:
                        if element_type in ["ApplicationComponent", "TechnologyService", "Product"]:
                            from app.models.vendor.vendor_organization import VendorProduct

                            # Check if this should be a vendor product
                            vendor_product = VendorProduct(
                                name=name,
                                description=elem.get("description", ""),
                                vendor_organization_id=target_vendor_id,
                                product_type=element_type,
                            )
                            db.session.add(vendor_product)
                            linked_to = {
                                "type": "vendor_product",
                                "id": target_vendor_id,
                                "product_name": name,
                            }
                    except Exception as vendor_link_error:
                        current_app.logger.warning(
                            f"Could not create vendor product: {vendor_link_error}"
                        )

                # Commit the savepoint
                savepoint.commit()

                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "id": new_element.id,
                        "status": "created",
                        "layer": layer,
                        "linked_to": linked_to,
                    }
                )
                created_count += 1

            except Exception as e:
                # Rollback only this element's savepoint, not the entire transaction
                try:
                    savepoint.rollback()
                except Exception as rollback_err:
                    current_app.logger.debug("Savepoint already rolled back: %s", rollback_err)
                errors.append(f"Error creating {element_type} '{name}': {str(e)}")
                current_app.logger.error(f"Error creating element {name}: {e}", exc_info=True)

        # Commit all successfully created elements
        if created_count > 0:
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Error committing elements: {commit_error}")
                errors.append(f"Failed to commit created elements: {str(commit_error)}")

        # Update upload record with results
        import time  # dead-code-ok

        # Helper function to safely serialize JSON
        def safe_json_dumps(data):
            """Safely serialize data to JSON, handling errors."""
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                current_app.logger.warning(f"JSON serialization error: {e}")
                return json.dumps(
                    {"error": f"Serialization error: {str(e)}", "data_type": str(type(data))}
                )

        # Update upload record with results using consolidated retry logic
        def update_upload_results():
            db.session.refresh(upload_record)

            upload_record.status = "completed" if not errors else "partial"
            upload_record.upload_progress = 100
            upload_record.created_elements_count = created_count
            upload_record.created_elements_details = safe_json_dumps(created_elements)
            upload_record.errors = safe_json_dumps(errors) if errors else None
            upload_record.confidence = extracted_data.get("metadata", {}).get(
                "confidence", "medium"
            )
            upload_record.chat_context_summary = (
                extracted_data.get("metadata", {}).get("notes", "") or ""
            )
            # Truncate chat_context_summary if too long
            if len(upload_record.chat_context_summary) > 1000:
                upload_record.chat_context_summary = (
                    upload_record.chat_context_summary[:1000] + "..."
                )

            # Safely serialize analysis results
            try:
                upload_record.analysis_results = safe_json_dumps(extracted_data)
                current_app.logger.info(
                    f"Saved analysis results: {len(archimate_elements)} elements, {len(relationships)} relationships"
                )
            except Exception as e:
                current_app.logger.error(f"Error serializing analysis results: {e}")
                upload_record.analysis_results = safe_json_dumps(
                    {
                        "error": "Failed to serialize analysis results",
                        "elements_count": len(archimate_elements),
                        "relationships_count": len(relationships),
                        "extraction_error": str(e),
                    }
                )

            upload_record.analyzed_at = datetime.utcnow()
            db.session.commit()

        success, _, error = execute_with_db_retry(
            update_upload_results, operation_name="update upload results"
        )

        if not success:
            current_app.logger.error(f"Failed to update upload record: {error}")
            raise Exception(f"Failed to save analysis results: {error}")

        return jsonify(
            {
                "success": True,
                "message": f"Document analyzed. Created {created_count} new ArchiMate elements.",
                "upload_id": upload_record.id,
                "analysis_results": {
                    "extracted_elements": len(archimate_elements),
                    "created_elements": created_count,
                    "created_details": created_elements,
                    "errors": errors,
                    "relationships_found": len(relationships),
                    "file_name": filename,
                    "confidence": upload_record.confidence,
                    "chat_context_summary": upload_record.chat_context_summary,
                },
                "document_path": file_path,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading document: {e}", exc_info=True)

        # Update upload record with error
        try:
            if "upload_record" in locals():
                upload_record.status = "failed"
                upload_record.errors = json.dumps([str(e)])
                db.session.commit()
        except Exception as record_update_error:
            current_app.logger.warning(
                f"Failed to update upload record with error status: {record_update_error}"
            )
            # Attempt one more rollback to clean up
            try:
                db.session.rollback()
            except Exception as e:
                logger.debug("Final session rollback failed: %s", e)

        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/documents/<int:doc_id>", methods=["GET"])
@login_required
def get_document_details(doc_id):
    """Get detailed information about a specific uploaded document."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found"}), 404

        # Parse analysis results
        analysis_results = None
        if document.analysis_results:
            try:
                analysis_results = (
                    json.loads(document.analysis_results)
                    if isinstance(document.analysis_results, str)
                    else document.analysis_results
                )
            except (json.JSONDecodeError, TypeError):
                analysis_results = {"error": "Failed to parse analysis results"}

        return jsonify(
            {
                "success": True,
                "document": {
                    "id": document.id,
                    "filename": document.original_filename,
                    "file_name": document.file_name,
                    "file_size": document.file_size,
                    "file_type": document.file_type,
                    "status": document.status,
                    "uploaded_at": document.created_at.isoformat() if document.created_at else None,
                    "analyzed_at": document.analyzed_at.isoformat()
                    if document.analyzed_at
                    else None,
                    "created_elements_count": document.created_elements_count,
                    "confidence": document.confidence,
                    "summary": document.chat_context_summary,
                    "analysis_results": analysis_results,
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error getting document details: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/documents", methods=["GET"])
@login_required
def get_document_history():
    """Get list of uploaded documents for the current user."""
    try:
        from app.models.ai_chat_document import AIChatDocumentUpload

        # Get query parameters with pagination bounds checking
        from app.utils.pagination import get_pagination_params

        # Note: get_pagination_params uses page/per_page, but this endpoint uses limit/offset
        # So we'll use a similar pattern for consistency
        MAX_LIMIT = 1000  # Maximum records per request
        DEFAULT_LIMIT = 50
        try:
            limit = int(request.args.get("limit", DEFAULT_LIMIT))
            limit = min(max(limit, 1), MAX_LIMIT)  # Clamp between 1 and MAX_LIMIT
        except (ValueError, TypeError):
            limit = DEFAULT_LIMIT

        try:
            offset = int(request.args.get("offset", 0))
            offset = max(offset, 0)  # Ensure non-negative
        except (ValueError, TypeError):
            offset = 0

        status_filter = request.args.get("status")  # Optional status filter

        # Build query
        query = AIChatDocumentUpload.query.filter_by(uploaded_by_id=current_user.id)

        if status_filter:
            query = query.filter_by(status=status_filter)

        # Order by most recent first
        query = query.order_by(AIChatDocumentUpload.created_at.desc())

        # Get total count
        total = query.count()

        # Get paginated results
        documents = query.limit(limit).offset(offset).all()

        return jsonify(
            {
                "success": True,
                "documents": [doc.to_dict() for doc in documents],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching document history: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    """Delete an uploaded document record."""
    try:
        from werkzeug.exceptions import NotFound

        from app.models.ai_chat_document import AIChatDocumentUpload

        current_app.logger.info(
            f"Delete request for document ID: {doc_id}, user ID: {current_user.id}"
        )

        # Try to find the document - check both with and without user filter first
        document = AIChatDocumentUpload.query.filter_by(id=doc_id).first()

        if not document:
            current_app.logger.warning(f"Document {doc_id} not found")
            return jsonify({"success": False, "error": "Document not found"}), 404

        # Check ownership
        if document.uploaded_by_id != current_user.id:
            current_app.logger.warning(
                f"User {current_user.id} attempted to delete document {doc_id} owned by {document.uploaded_by_id}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Unauthorized - you can only delete your own documents",
                    }
                ),
                403,
            )

        # Delete file if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                current_app.logger.warning(f"Could not delete file {document.file_path}: {e}")

        # Delete database record
        db.session.delete(document)
        db.session.commit()

        return jsonify({"success": True, "message": "Document deleted successfully"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting document: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/documents/<int:doc_id>/re-analyze", methods=["POST"])
@login_required
def re_analyze_document(doc_id):
    """Re-analyze a previously uploaded document."""
    try:
        from app.archimate_crud.routes import MODEL_REGISTRY
        from app.models.ai_chat_document import AIChatDocumentUpload
        from app.services.archimate.document_analysis_service import DocumentAnalysisService
        from app.services.core.retry_handler import execute_with_db_retry

        document = AIChatDocumentUpload.query.filter_by(
            id=doc_id, uploaded_by_id=current_user.id
        ).first()

        if not document:
            return jsonify({"success": False, "error": "Document not found or unauthorized"}), 404

        # Check if file still exists
        if not document.file_path or not os.path.exists(document.file_path):
            return jsonify({"success": False, "error": "File no longer exists"}), 404

        # Update status
        document.status = "analyzing"
        document.upload_progress = 0
        db.session.commit()

        # Analyze document
        analysis_service = DocumentAnalysisService()

        # Get or create event loop for async operations
        loop = get_or_create_event_loop()

        if document.file_type == "image":
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_image(
                    document.file_path, document.provider, "architecture"
                )
            )
        elif document.file_type == "document":
            extracted_data, interactions = loop.run_until_complete(
                analysis_service._analyze_document(
                    document.file_path, document.provider, "architecture"
                )
            )
            interaction = interactions[0] if interactions else None
        else:
            extracted_data, interaction = loop.run_until_complete(
                analysis_service._analyze_text_file(
                    document.file_path, document.provider, "architecture"
                )
            )

        # Extract and create elements (same logic as upload)
        archimate_elements = extracted_data.get("elements", [])
        created_elements = []
        created_count = 0
        errors = []

        # Batch-prefetch existing names per model class to avoid N+1 queries
        existing_names_by_type = {}
        for elem in archimate_elements:
            etype = elem.get("type")
            mc = MODEL_REGISTRY.get(etype)
            if mc and etype not in existing_names_by_type:
                existing_names_by_type[etype] = {
                    row.name for row in mc.query.with_entities(mc.name).all()  # model-safety-ok: batch prefetch
                }

        for elem in archimate_elements:
            try:
                element_type = elem.get("type")
                model_class = MODEL_REGISTRY.get(element_type)
                if not model_class:
                    errors.append(f"Element type '{element_type}' not supported")
                    continue

                name = elem.get("name", "")
                if name in existing_names_by_type.get(element_type, set()):
                    continue

                element_data = {"name": name, "description": elem.get("description", "")}

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = current_user.id

                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()

                # Auto-create ArchiMateElement link if the model has archimate_element_id
                if hasattr(new_element, "archimate_element_id"):  # model-safety-ok: dynamic model class
                    from app.models.archimate_core import ArchiMateElement

                    layer = elem.get("layer", "")
                    archimate_element = ArchiMateElement(
                        name=name,
                        type=element_type,  # Use 'type' not 'element_type'
                        layer=layer if layer else None,
                        description=elem.get("description", ""),
                    )
                    db.session.add(archimate_element)
                    db.session.flush()
                    new_element.archimate_element_id = archimate_element.id

                created_elements.append(
                    {"type": element_type, "name": name, "id": new_element.id, "status": "created"}
                )
                created_count += 1

            except Exception as e:
                errors.append(f"Error creating {elem.get('type', 'unknown')}: {str(e)}")

        if created_count > 0:
            db.session.commit()

        # Update document record with consolidated retry logic
        def safe_json_dumps(data):
            """Safely serialize data to JSON."""
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                current_app.logger.warning(f"JSON serialization error: {e}")
                return json.dumps({"error": f"Serialization error: {str(e)}"})

        def update_document_results():
            db.session.refresh(document)
            document.status = "completed" if not errors else "partial"
            document.upload_progress = 100
            document.created_elements_count = created_count
            document.created_elements_details = safe_json_dumps(created_elements)
            document.errors = safe_json_dumps(errors) if errors else None
            document.confidence = extracted_data.get("metadata", {}).get("confidence", "medium")
            document.analysis_results = safe_json_dumps(extracted_data)
            document.analyzed_at = datetime.utcnow()
            db.session.commit()

        success, _, error = execute_with_db_retry(
            update_document_results, operation_name="update re-analysis results"
        )

        if not success:
            current_app.logger.error(f"Failed to update document record: {error}")
            raise Exception(f"Failed to save re-analysis results: {error}")

        return jsonify(
            {
                "success": True,
                "message": f"Document re-analyzed. Created {created_count} new elements.",
                "analysis_results": {
                    "created_elements": created_count,
                    "created_details": created_elements,
                    "errors": errors,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error re-analyzing document: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/create-elements", methods=["POST"])
@login_required
def create_elements():
    """
    Create ArchiMate elements from user-selected preview list.

    This endpoint is called after preview mode to create only the elements
    the user has selected and optionally edited.

    Expected JSON body:
    {
        "elements": [{"name": "...", "type": "...", "description": "...", "layer": "..."}],
        "analysis_context": "general|application|vendor",
        "target_application_id": 123,  # optional
        "target_vendor_id": 456  # optional
    }
    """
    try:
        from app.archimate_crud.routes import MODEL_REGISTRY
        from app.models.archimate_core import ArchiMateElement

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        elements = data.get("elements", [])
        if not elements:
            return jsonify({"success": False, "error": "No elements provided"}), 400

        analysis_context = data.get("analysis_context", "general")
        target_application_id = data.get("target_application_id")
        target_vendor_id = data.get("target_vendor_id")

        # Convert IDs to integers if provided
        if target_application_id:
            try:
                target_application_id = int(target_application_id)
            except (ValueError, TypeError):
                target_application_id = None

        if target_vendor_id:
            try:
                target_vendor_id = int(target_vendor_id)
            except (ValueError, TypeError):
                target_vendor_id = None

        user_id = current_user.id if current_user.is_authenticated else None

        current_app.logger.info(
            f"Creating {len(elements)} elements - Context: {analysis_context}, App: {target_application_id}, Vendor: {target_vendor_id}"
        )

        created_elements = []
        created_count = 0
        errors = []

        # Import field mapper
        from app.ai_chat.element_field_mapper import (
            check_element_exists,
            map_element_data_to_model_fields,
        )

        for elem in elements:
            element_type = elem.get("type")
            name = elem.get("name", "").strip()
            layer = elem.get("layer", "").lower()
            description = elem.get("description", "")

            if not name:
                errors.append(f"Element with type '{element_type}' has no name - skipped")
                continue

            # Find the model class
            model_class = MODEL_REGISTRY.get(element_type)
            if not model_class:
                errors.append(f"Element type '{element_type}' not supported - skipped '{name}'")
                continue

            # Check if element already exists (using correct field name)
            existing = check_element_exists(model_class, element_type, name)
            if existing:
                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "id": existing.id,
                        "status": "skipped",
                        "reason": "Already exists",
                    }
                )
                continue

            # Use savepoint for each element
            try:
                savepoint = db.session.begin_nested()

                # Map element data to model-specific fields
                element_data = map_element_data_to_model_fields(element_type, elem, user_id)

                # Only add created_by_id if the model supports it
                if hasattr(model_class, "created_by_id"):
                    element_data["created_by_id"] = user_id

                # Create the element
                new_element = model_class(**element_data)
                db.session.add(new_element)
                db.session.flush()

                # Auto-create ArchiMateElement link
                archimate_element = ArchiMateElement(
                    name=name,
                    type=element_type,
                    layer=layer if layer else None,
                    description=description,
                )
                db.session.add(archimate_element)
                db.session.flush()

                # Link them
                if hasattr(new_element, "archimate_element_id"):  # model-safety-ok: dynamic model class
                    new_element.archimate_element_id = archimate_element.id

                # Link to target application or vendor if specified
                linked_to = None
                if target_application_id and analysis_context == "application":
                    if hasattr(new_element, "application_id"):  # model-safety-ok: dynamic model class
                        new_element.application_id = target_application_id
                        linked_to = {"type": "application", "id": target_application_id}
                    # Also add to relationship table if available
                    try:
                        from app.models.relationship_tables import application_component_elements

                        if element_type in [
                            "ApplicationService",
                            "ApplicationInterface",
                            "DataObject",
                            "ApplicationFunction",
                        ]:
                            db.session.execute(  # tenant-filtered: scoped via parent FK
                                application_component_elements.insert().values(
                                    application_component_id=target_application_id,
                                    archimate_element_id=archimate_element.id,
                                )
                            )
                            linked_to = {"type": "application", "id": target_application_id}
                    except Exception as link_error:
                        current_app.logger.warning(
                            f"Could not link element to application: {link_error}"
                        )

                elif target_vendor_id and analysis_context == "vendor":
                    if hasattr(new_element, "vendor_id"):  # model-safety-ok: dynamic model class
                        new_element.vendor_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    elif hasattr(new_element, "organization_id"):  # model-safety-ok: dynamic model class
                        new_element.organization_id = target_vendor_id
                        linked_to = {"type": "vendor", "id": target_vendor_id}
                    # For vendor products
                    try:
                        if element_type in ["ApplicationComponent", "TechnologyService", "Product"]:
                            from app.models.vendor.vendor_organization import VendorProduct

                            vendor_product = VendorProduct(
                                name=name,
                                description=description,
                                vendor_organization_id=target_vendor_id,
                                product_type=element_type,
                            )
                            db.session.add(vendor_product)
                            linked_to = {
                                "type": "vendor_product",
                                "id": target_vendor_id,
                                "product_name": name,
                            }
                    except Exception as vendor_link_error:
                        current_app.logger.warning(
                            f"Could not create vendor product: {vendor_link_error}"
                        )

                # Commit the savepoint
                savepoint.commit()

                created_elements.append(
                    {
                        "type": element_type,
                        "name": name,
                        "id": new_element.id,
                        "status": "created",
                        "layer": layer,
                        "linked_to": linked_to,
                    }
                )
                created_count += 1

            except Exception as e:
                try:
                    savepoint.rollback()
                except Exception as rollback_err:
                    current_app.logger.debug("Savepoint already rolled back: %s", rollback_err)
                errors.append(f"Error creating {element_type} '{name}': {str(e)}")
                current_app.logger.error(f"Error creating element {name}: {e}", exc_info=True)

        # Commit all successfully created elements
        if created_count > 0:
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Error committing elements: {commit_error}")
                errors.append(f"Failed to commit created elements: {str(commit_error)}")

        # Build response with links to view created elements
        view_links = {}
        if target_application_id and analysis_context == "application":
            view_links["application"] = f"/dashboard/application/{target_application_id}"
            view_links[
                "application_architecture"
            ] = f"/dashboard/application/{target_application_id}#architecture"
        if target_vendor_id and analysis_context == "vendor":
            view_links["vendor"] = f"/vendors/view/{target_vendor_id}"

        return jsonify(
            {
                "success": True,
                "message": f"Created {created_count} ArchiMate elements",
                "created_count": created_count,
                "created_elements": created_elements,
                "errors": errors,
                "view_links": view_links,
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating elements: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# =============================================================================
# AI Chat Extension Service Routes
# =============================================================================


@ai_chat.route("/extensions")
@login_required
def get_extension_capabilities():
    """Get available AI Chat extension capabilities."""
    try:
        chat_service = get_chat_service()
        capabilities = chat_service.get_extension_capabilities()
        return jsonify({"success": True, "capabilities": capabilities})
    except Exception as e:
        current_app.logger.error(f"Error getting extension capabilities: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/visual", methods=["POST"])
@login_required
def generate_visual():
    """Generate visual artifacts (diagrams, charts, graphs)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        visual_type = data.get("visual_type")
        if not visual_type:
            return jsonify({"success": False, "error": "visual_type is required"}), 400

        parameters = data.get("parameters", {})
        output_format = data.get("output_format", "mermaid")

        chat_service = get_chat_service()
        result = chat_service.generate_visual(visual_type, parameters, output_format)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error generating visual: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/scenario", methods=["POST"])
@login_required
def run_scenario_analysis():
    """Run what-if scenario analysis."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        scenario_type = data.get("scenario_type")
        if not scenario_type:
            return jsonify({"success": False, "error": "scenario_type is required"}), 400

        parameters = data.get("parameters", {})

        chat_service = get_chat_service()
        result = chat_service.run_scenario_analysis(scenario_type, parameters)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error running scenario analysis: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/actions", methods=["POST"])
@login_required
def create_automated_action():
    """Create an automated action."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        action_type = data.get("action_type")
        if not action_type:
            return jsonify({"success": False, "error": "action_type is required"}), 400

        parameters = data.get("parameters", {})

        chat_service = get_chat_service()
        result = chat_service.create_automated_action(action_type, parameters, current_user.id)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error creating automated action: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/analytics", methods=["POST"])
@login_required
def get_advanced_analytics():
    """Get advanced analytics results."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        analytics_type = data.get("analytics_type")
        if not analytics_type:
            return jsonify({"success": False, "error": "analytics_type is required"}), 400

        parameters = data.get("parameters", {})

        chat_service = get_chat_service()
        result = chat_service.get_advanced_analytics(analytics_type, parameters)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting advanced analytics: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/compliance", methods=["POST"])
@login_required
def check_compliance():
    """Check compliance against standards and regulations."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        check_type = data.get("check_type")
        if not check_type:
            return jsonify({"success": False, "error": "check_type is required"}), 400

        parameters = data.get("parameters", {})

        chat_service = get_chat_service()
        result = chat_service.check_compliance(check_type, parameters)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error checking compliance: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/predictions", methods=["POST"])
@login_required
def get_predictive_insights():
    """Get predictive insights and forecasts."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        prediction_type = data.get("prediction_type")
        if not prediction_type:
            return jsonify({"success": False, "error": "prediction_type is required"}), 400

        parameters = data.get("parameters", {})

        chat_service = get_chat_service()
        result = chat_service.get_predictive_insights(prediction_type, parameters)

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting predictive insights: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/analytics/portfolio-health")
@login_required
def get_portfolio_health():
    """Quick endpoint to get portfolio health score."""
    try:
        scope = request.args.get("scope", "all")

        chat_service = get_chat_service()
        result = chat_service.get_advanced_analytics("portfolio_health", {"scope": scope})

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting portfolio health: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/predictions/dashboard")
@login_required
def get_predictive_dashboard():
    """Get predictive insights dashboard for the current user."""
    try:
        persona = request.args.get("persona")

        chat_service = get_chat_service()
        result = chat_service.get_predictive_insights("dashboard", {"persona": persona})

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting predictive dashboard: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@ai_chat.route("/extensions/compliance/frameworks")
@login_required
def get_compliance_frameworks():
    """Get available compliance frameworks."""
    try:
        chat_service = get_chat_service()
        frameworks = chat_service.compliance_standards.get_available_frameworks()

        return jsonify({"success": True, "frameworks": frameworks})
    except Exception as e:
        current_app.logger.error(f"Error getting compliance frameworks: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
