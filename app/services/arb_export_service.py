"""
ARB Export Service

Provides export functionality for ARB data including:
- CSV export for review items, sessions, exceptions
- Excel export with formatting and multiple sheets
- PDF export for reports and documentation
"""

import csv
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logging.warning("Pandas not available - Excel export functionality limited")

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("ReportLab not available - PDF export functionality limited")

from app import db
from app.models.architecture_review_board import (
    ARBAuditLog,
    ARBException,
    ARBReviewItem,
    ARBSession,
)

logger = logging.getLogger(__name__)


class ARBExportService:
    """
    Service for exporting ARB data in various formats.
    """

    def __init__(self):
        self.supported_formats = ["csv", "excel", "pdf"]

    # =========================================================================
    # CSV EXPORTS
    # =========================================================================

    def export_reviews_to_csv(
        self,
        reviews: List[ARBReviewItem],
    ) -> str:
        """
        Export review items to CSV format.

        Args:
            reviews: List of ARBReviewItem objects

        Returns:
            CSV content as string
        """
        headers = [
            "Review Number",
            "Title",
            "Review Type",
            "Status",
            "Priority",
            "TOGAF Phase",
            "ArchiMate Layer",
            "Business Impact",
            "Governance Score",
            "Readiness Score",
            "Submitted By",
            "Submitted Date",
            "Session",
            "Decision",
            "Decision Date",
            "Approved By",
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for review in reviews:
            row = [
                review.review_number,
                review.title,
                review.review_type,
                review.status,
                review.priority,
                review.togaf_phase,
                review.archimate_layer,
                review.business_impact,
                review.overall_score,
                review.readiness_score,
                review.submitter.email if review.submitter else "",
                review.submitted_at.strftime("%Y-%m-%d") if review.submitted_at else "",
                review.arb_session.session_number if review.arb_session else "",
                review.decision,
                review.decision_date.strftime("%Y-%m-%d") if review.decision_date else "",
                review.decided_by.email if review.decided_by else "",
            ]
            writer.writerow(row)

        content = output.getvalue()
        output.close()

        logger.info(f"CSV export completed: {len(reviews)} reviews")
        return content

    def export_sessions_to_csv(
        self,
        sessions: List[ARBSession],
    ) -> str:
        """
        Export sessions to CSV format.

        Args:
            sessions: List of ARBSession objects

        Returns:
            CSV content as string
        """
        headers = [
            "Session Number",
            "Session Type",
            "Status",
            "Scheduled Date",
            "Location",
            "Chair",
            "Secretary",
            "Review Count",
            "Agenda Items",
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for session in sessions:
            row = [
                session.session_number,
                session.session_type,
                session.status,
                session.scheduled_date.strftime("%Y-%m-%d %H:%M") if session.scheduled_date else "",
                session.location,
                session.chair.email if session.chair else "",
                session.secretary.email if session.secretary else "",
                len(session.review_items) if session.review_items else 0,
                len(session.agenda_items) if session.agenda_items else 0,
            ]
            writer.writerow(row)

        content = output.getvalue()
        output.close()

        logger.info(f"CSV export completed: {len(sessions)} sessions")
        return content

    def export_exceptions_to_csv(
        self,
        exceptions: List[ARBException],
    ) -> str:
        """
        Export exceptions to CSV format.

        Args:
            exceptions: List of ARBException objects

        Returns:
            CSV content as string
        """
        headers = [
            "Exception Number",
            "Exception Type",
            "Status",
            "Standard Code",
            "Standard Name",
            "Exception Reason",
            "Business Justification",
            "Requested By",
            "Requested Date",
            "Approved By",
            "Approved Date",
            "Expires At",
            "Renewal Count",
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for exc in exceptions:
            row = [
                exc.exception_number,
                exc.exception_type,
                exc.status,
                exc.standard.code if exc.standard else "",
                exc.standard.name if exc.standard else "",
                exc.exception_reason,
                exc.business_justification or "",
                exc.requester.email if exc.requester else "",
                exc.requested_at.strftime("%Y-%m-%d") if exc.requested_at else "",
                exc.approver.email if exc.approver else "",
                exc.approved_at.strftime("%Y-%m-%d") if exc.approved_at else "",
                exc.expires_at.strftime("%Y-%m-%d") if exc.expires_at else "",
                exc.renewal_count,
            ]
            writer.writerow(row)

        content = output.getvalue()
        output.close()

        logger.info(f"CSV export completed: {len(exceptions)} exceptions")
        return content

    def export_audit_log_to_csv(
        self,
        logs: List[ARBAuditLog],
    ) -> str:
        """
        Export audit logs to CSV format.

        Args:
            logs: List of ARBAuditLog objects

        Returns:
            CSV content as string
        """
        headers = [
            "Timestamp",
            "Entity Type",
            "Entity ID",
            "Entity Reference",
            "Action",
            "Description",
            "User",
            "IP Address",
            "Changed Fields",
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        for log in logs:
            changed = ", ".join(log.changed_fields) if log.changed_fields else ""
            row = [
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
                log.entity_type,
                log.entity_id,
                log.entity_reference or "",
                log.action,
                log.action_description or "",
                log.user_email or "",
                log.ip_address or "",
                changed,
            ]
            writer.writerow(row)

        content = output.getvalue()
        output.close()

        logger.info(f"CSV export completed: {len(logs)} audit entries")
        return content

    # =========================================================================
    # EXCEL EXPORTS
    # =========================================================================

    def export_reviews_to_excel(
        self,
        reviews: List[ARBReviewItem],
        include_summary: bool = True,
    ) -> bytes:
        """
        Export review items to Excel with formatting.

        Args:
            reviews: List of ARBReviewItem objects
            include_summary: Include summary sheet

        Returns:
            Excel file content as bytes
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("Pandas is required for Excel export")

        # Build review data
        data = []
        for review in reviews:
            data.append(
                {
                    "Review Number": review.review_number,
                    "Title": review.title,
                    "Review Type": review.review_type,
                    "Status": review.status,
                    "Priority": review.priority,
                    "TOGAF Phase": review.togaf_phase,
                    "ArchiMate Layer": review.archimate_layer,
                    "Business Impact": review.business_impact,
                    "Governance Score": review.overall_score,
                    "Readiness Score": review.readiness_score,
                    "Submitted By": review.submitter.email if review.submitter else "",
                    "Submitted Date": review.submitted_at.strftime("%Y-%m-%d")
                    if review.submitted_at
                    else "",
                    "Decision": review.decision,
                    "Decision Date": review.decision_date.strftime("%Y-%m-%d")
                    if review.decision_date
                    else "",
                }
            )

        df_reviews = pd.DataFrame(data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Main data sheet
            df_reviews.to_excel(writer, sheet_name="Reviews", index=False)

            if include_summary:
                # Summary statistics
                summary_data = {
                    "Metric": [
                        "Total Reviews",
                        "Pending",
                        "Approved",
                        "Rejected",
                        "Avg Governance Score",
                        "Avg Readiness Score",
                    ],
                    "Value": [
                        len(reviews),
                        len([r for r in reviews if r.status == "pending"]),
                        len([r for r in reviews if r.status == "approved"]),
                        len([r for r in reviews if r.status == "rejected"]),
                        round(sum(r.overall_score or 0 for r in reviews) / len(reviews), 1)
                        if reviews
                        else 0,
                        round(sum(r.readiness_score or 0 for r in reviews) / len(reviews), 1)
                        if reviews
                        else 0,
                    ],
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name="Summary", index=False)

            # Apply formatting
            workbook = writer.book
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = max(len(str(cell.value or "")) for cell in column)
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

        excel_content = output.getvalue()
        output.close()

        logger.info(f"Excel export completed: {len(reviews)} reviews")
        return excel_content

    def export_session_summary_to_excel(
        self,
        session: ARBSession,
    ) -> bytes:
        """
        Export a single session with all details to Excel.

        Args:
            session: ARBSession object

        Returns:
            Excel file content as bytes
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("Pandas is required for Excel export")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Session info sheet
            session_data = {
                "Field": [
                    "Session Number",
                    "Type",
                    "Status",
                    "Scheduled Date",
                    "Location",
                    "Chair",
                    "Secretary",
                    "Meeting Link",
                ],
                "Value": [
                    session.session_number,
                    session.session_type,
                    session.status,
                    session.scheduled_date.strftime("%Y-%m-%d %H:%M")
                    if session.scheduled_date
                    else "",
                    session.location or "",
                    session.chair.email if session.chair else "",
                    session.secretary.email if session.secretary else "",
                    session.meeting_link or "",
                ],
            }
            df_session = pd.DataFrame(session_data)
            df_session.to_excel(writer, sheet_name="Session Info", index=False)

            # Reviews sheet
            if session.review_items:
                review_data = []
                for review in session.review_items:
                    review_data.append(
                        {
                            "Review Number": review.review_number,
                            "Title": review.title,
                            "Type": review.review_type,
                            "Status": review.status,
                            "Priority": review.priority,
                            "Decision": review.decision or "",
                            "Governance Score": review.overall_score,
                        }
                    )
                df_reviews = pd.DataFrame(review_data)
                df_reviews.to_excel(writer, sheet_name="Review Items", index=False)

            # Agenda sheet
            if session.agenda_items:
                agenda_data = []
                for i, item in enumerate(session.agenda_items, 1):
                    agenda_data.append(
                        {
                            "Order": i,
                            "Topic": item.get("topic", ""),
                            "Duration": item.get("duration", ""),
                            "Presenter": item.get("presenter", ""),
                            "Notes": item.get("notes", ""),
                        }
                    )
                df_agenda = pd.DataFrame(agenda_data)
                df_agenda.to_excel(writer, sheet_name="Agenda", index=False)

            # Format worksheets
            workbook = writer.book
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = max(len(str(cell.value or "")) for cell in column)
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

        excel_content = output.getvalue()
        output.close()

        logger.info(f"Session Excel export completed: {session.session_number}")
        return excel_content

    # =========================================================================
    # PDF EXPORTS
    # =========================================================================

    def export_reviews_to_pdf(
        self,
        reviews: List[ARBReviewItem],
        title: str = "ARB Review Items Report",
    ) -> bytes:
        """
        Export review items to PDF format.

        Args:
            reviews: List of ARBReviewItem objects
            title: Report title

        Returns:
            PDF content as bytes
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF export")

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=30,
        )
        elements.append(Paragraph(title, title_style))

        # Generated date
        elements.append(
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"])
        )
        elements.append(Spacer(1, 20))

        # Summary statistics
        summary_title = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=10,
        )
        elements.append(Paragraph("Summary", summary_title))

        total = len(reviews)
        pending = len([r for r in reviews if r.status == "pending"])
        approved = len([r for r in reviews if r.status == "approved"])
        rejected = len([r for r in reviews if r.status == "rejected"])

        summary_data = [
            ["Total Reviews", str(total)],
            ["Pending", str(pending)],
            ["Approved", str(approved)],
            ["Rejected", str(rejected)],
        ]

        summary_table = Table(summary_data, colWidths=[2 * inch, 1 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Reviews table
        elements.append(Paragraph("Review Items", summary_title))

        table_data = [["#", "Title", "Type", "Status", "Score"]]
        for review in reviews[:50]:  # Limit to 50 for PDF
            table_data.append(
                [
                    review.review_number,
                    review.title[:40] + "..." if len(review.title) > 40 else review.title,
                    review.review_type,
                    review.status,
                    str(review.overall_score or "-"),
                ]
            )

        review_table = Table(
            table_data, colWidths=[1 * inch, 3 * inch, 1.5 * inch, 1 * inch, 0.75 * inch]
        )
        review_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(review_table)

        doc.build(elements)

        pdf_content = output.getvalue()
        output.close()

        logger.info(f"PDF export completed: {len(reviews)} reviews")
        return pdf_content

    def export_session_to_pdf(
        self,
        session: ARBSession,
    ) -> bytes:
        """
        Export a session summary to PDF.

        Args:
            session: ARBSession object

        Returns:
            PDF content as bytes
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF export")

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=10,
        )
        elements.append(Paragraph(f"ARB Session: {session.session_number}", title_style))
        elements.append(Spacer(1, 20))

        # Session details
        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=10,
        )
        elements.append(Paragraph("Session Details", section_style))

        details_data = [
            ["Type", session.session_type],
            ["Status", session.status],
            [
                "Date",
                session.scheduled_date.strftime("%Y-%m-%d %H:%M")
                if session.scheduled_date
                else "-",
            ],
            ["Location", session.location or "-"],
            ["Chair", session.chair.email if session.chair else "-"],
            ["Secretary", session.secretary.email if session.secretary else "-"],
        ]

        details_table = Table(details_data, colWidths=[2 * inch, 4 * inch])
        details_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(details_table)
        elements.append(Spacer(1, 20))

        # Agenda
        if session.agenda_items:
            elements.append(Paragraph("Agenda", section_style))

            agenda_data = [["#", "Topic", "Duration", "Presenter"]]
            for i, item in enumerate(session.agenda_items, 1):
                agenda_data.append(
                    [
                        str(i),
                        item.get("topic", "-"),
                        item.get("duration", "-"),
                        item.get("presenter", "-"),
                    ]
                )

            agenda_table = Table(
                agenda_data, colWidths=[0.5 * inch, 4 * inch, 1 * inch, 1.5 * inch]
            )
            agenda_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("PADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(agenda_table)
            elements.append(Spacer(1, 20))

        # Review items
        if session.review_items:
            elements.append(Paragraph("Review Items", section_style))

            review_data = [["#", "Title", "Type", "Decision"]]
            for review in session.review_items:
                review_data.append(
                    [
                        review.review_number,
                        review.title[:35] + "..." if len(review.title) > 35 else review.title,
                        review.review_type,
                        review.decision or "-",
                    ]
                )

            review_table = Table(
                review_data, colWidths=[1 * inch, 3.5 * inch, 1.5 * inch, 1 * inch]
            )
            review_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("PADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(review_table)

        doc.build(elements)

        pdf_content = output.getvalue()
        output.close()

        logger.info(f"Session PDF export completed: {session.session_number}")
        return pdf_content


# Create singleton instance
arb_export_service = ARBExportService()
