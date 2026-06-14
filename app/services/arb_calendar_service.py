"""
ARB Calendar Service

Provides iCal/ICS calendar integration for ARB sessions including:
- Single event ICS generation
- Multi-event calendar feeds
- Session template scheduling
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app import db
from app.models.architecture_review_board import ARBSession, ARBSessionTemplate

logger = logging.getLogger(__name__)


class ARBCalendarService:
    """
    Service for ARB calendar/ICS integration.
    """

    # iCal date format
    ICAL_DATE_FORMAT = "%Y%m%dT%H%M%SZ"
    ICAL_DATE_ONLY_FORMAT = "%Y%m%d"

    def __init__(self):
        self.calendar_name = "ARB Sessions"
        self.calendar_prodid = "-//Enterprise Architecture//ARB Calendar//EN"

    def generate_ics_event(
        self,
        session: ARBSession,
        include_reviews: bool = True,
    ) -> str:
        """
        Generate an ICS file for a single session.

        Args:
            session: ARBSession object
            include_reviews: Include review items in description

        Returns:
            ICS file content as string
        """
        # Build event UID
        uid = f"arb-session-{session.id}@enterprise-arch"

        # Format dates
        if session.scheduled_date:
            dtstart = session.scheduled_date.strftime(self.ICAL_DATE_FORMAT)
            # Assume 2 - hour sessions by default
            duration = (
                session.duration_minutes
                if hasattr(session, "duration_minutes") and session.duration_minutes
                else 120
            )
            end_time = session.scheduled_date + timedelta(minutes=duration)
            dtend = end_time.strftime(self.ICAL_DATE_FORMAT)
        else:
            # Default to today if no date
            now = datetime.utcnow()
            dtstart = now.strftime(self.ICAL_DATE_FORMAT)
            dtend = (now + timedelta(hours=2)).strftime(self.ICAL_DATE_FORMAT)

        # Build description
        description_lines = [
            f"ARB Session: {session.session_number}",
            f"Type: {session.session_type}",
            f"Status: {session.status}",
            "",
        ]

        if session.chair:
            description_lines.append(f"Chair: {session.chair.email}")
        if session.secretary:
            description_lines.append(f"Secretary: {session.secretary.email}")

        if include_reviews and session.review_items:
            description_lines.append("")
            description_lines.append("Review Items:")
            for review in session.review_items:
                description_lines.append(f"- {review.review_number}: {review.title}")

        if session.agenda_items:
            description_lines.append("")
            description_lines.append("Agenda:")
            for i, item in enumerate(session.agenda_items, 1):
                topic = item.get("topic", "")
                duration = item.get("duration", "")
                description_lines.append(f"{i}. {topic} ({duration})")

        description = "\\n".join(description_lines)

        # Build location
        location = session.location or ""
        if session.meeting_link:
            if location:
                location += " | "
            location += session.meeting_link

        # Build summary
        summary = f"ARB: {session.session_number} - {session.session_type}"

        # Generate ICS content
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{self.calendar_prodid}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime(self.ICAL_DATE_FORMAT)}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{self._escape_ical_text(summary)}",
            f"DESCRIPTION:{self._escape_ical_text(description)}",
        ]

        if location:
            ics_lines.append(f"LOCATION:{self._escape_ical_text(location)}")

        # Add organizer if chair exists
        if session.chair:
            ics_lines.append(f"ORGANIZER:mailto:{session.chair.email}")

        # Add status
        status_map = {
            "scheduled": "CONFIRMED",
            "in_progress": "CONFIRMED",
            "completed": "CONFIRMED",
            "cancelled": "CANCELLED",
        }
        ics_status = status_map.get(session.status, "TENTATIVE")
        ics_lines.append(f"STATUS:{ics_status}")

        # Add categories
        ics_lines.append("CATEGORIES:ARB,Architecture Review")

        ics_lines.extend(
            [
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )

        return "\r\n".join(ics_lines)

    def generate_ics_calendar(
        self,
        sessions: List[ARBSession],
        calendar_name: str = None,
    ) -> str:
        """
        Generate an ICS calendar with multiple sessions.

        Args:
            sessions: List of ARBSession objects
            calendar_name: Optional custom calendar name

        Returns:
            ICS file content as string
        """
        cal_name = calendar_name or self.calendar_name

        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{self.calendar_prodid}",
            f"X-WR-CALNAME:{cal_name}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        for session in sessions:
            event_content = self._generate_vevent(session)
            ics_lines.append(event_content)

        ics_lines.append("END:VCALENDAR")

        return "\r\n".join(ics_lines)

    def _generate_vevent(
        self,
        session: ARBSession,
    ) -> str:
        """
        Generate VEVENT component for a session.

        Args:
            session: ARBSession object

        Returns:
            VEVENT string
        """
        uid = f"arb-session-{session.id}@enterprise-arch"

        if session.scheduled_date:
            dtstart = session.scheduled_date.strftime(self.ICAL_DATE_FORMAT)
            duration = getattr(session, "duration_minutes", 120) or 120
            end_time = session.scheduled_date + timedelta(minutes=duration)
            dtend = end_time.strftime(self.ICAL_DATE_FORMAT)
        else:
            now = datetime.utcnow()
            dtstart = now.strftime(self.ICAL_DATE_FORMAT)
            dtend = (now + timedelta(hours=2)).strftime(self.ICAL_DATE_FORMAT)

        summary = f"ARB: {session.session_number}"
        description = f"Type: {session.session_type}\\nStatus: {session.status}"

        if session.review_items:
            description += f"\\n\\nReview Items: {len(session.review_items)}"

        location = session.location or ""
        if session.meeting_link:
            location = (
                session.meeting_link if not location else f"{location} | {session.meeting_link}"
            )

        lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime(self.ICAL_DATE_FORMAT)}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{self._escape_ical_text(summary)}",
            f"DESCRIPTION:{self._escape_ical_text(description)}",
        ]

        if location:
            lines.append(f"LOCATION:{self._escape_ical_text(location)}")

        if session.chair:
            lines.append(f"ORGANIZER:mailto:{session.chair.email}")

        lines.append("END:VEVENT")

        return "\r\n".join(lines)

    def get_upcoming_sessions_feed(
        self,
        days_ahead: int = 90,
    ) -> str:
        """
        Generate ICS feed for upcoming sessions.

        Args:
            days_ahead: Number of days to include

        Returns:
            ICS file content
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_ahead)

        sessions = (
            ARBSession.query.filter(
                ARBSession.scheduled_date >= now,
                ARBSession.scheduled_date <= cutoff,
                ARBSession.status != "cancelled",
            )
            .order_by(ARBSession.scheduled_date)
            .all()
        )

        return self.generate_ics_calendar(
            sessions,
            calendar_name=f"Upcoming ARB Sessions ({days_ahead} days)",
        )

    def create_meeting_invite(
        self,
        session: ARBSession,
        attendee_emails: List[str],
    ) -> str:
        """
        Create a meeting invitation ICS with attendees.

        Args:
            session: ARBSession object
            attendee_emails: List of attendee email addresses

        Returns:
            ICS file content with RSVP
        """
        uid = f"arb-session-{session.id}-{uuid4().hex[:8]}@enterprise-arch"

        if session.scheduled_date:
            dtstart = session.scheduled_date.strftime(self.ICAL_DATE_FORMAT)
            duration = getattr(session, "duration_minutes", 120) or 120
            end_time = session.scheduled_date + timedelta(minutes=duration)
            dtend = end_time.strftime(self.ICAL_DATE_FORMAT)
        else:
            now = datetime.utcnow()
            dtstart = now.strftime(self.ICAL_DATE_FORMAT)
            dtend = (now + timedelta(hours=2)).strftime(self.ICAL_DATE_FORMAT)

        summary = f"ARB Session: {session.session_number}"
        description = f"Architecture Review Board Session\\n\\nType: {session.session_type}"

        if session.review_items:
            description += "\\n\\nReview Items:"
            for review in session.review_items:
                description += f"\\n- {review.review_number}: {review.title}"

        location = session.location or ""
        if session.meeting_link:
            location = (
                session.meeting_link if not location else f"{location}\\n{session.meeting_link}"
            )

        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{self.calendar_prodid}",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime(self.ICAL_DATE_FORMAT)}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{self._escape_ical_text(summary)}",
            f"DESCRIPTION:{self._escape_ical_text(description)}",
        ]

        if location:
            ics_lines.append(f"LOCATION:{self._escape_ical_text(location)}")

        # Add organizer
        if session.chair:
            ics_lines.append(
                f"ORGANIZER;CN={session.chair.display_name or session.chair.email}:mailto:{session.chair.email}"
            )

        # Add attendees
        for email in attendee_emails:
            ics_lines.append(f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:{email}")

        ics_lines.extend(
            [
                "SEQUENCE:0",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )

        return "\r\n".join(ics_lines)

    def _escape_ical_text(self, text: str) -> str:
        """
        Escape special characters for iCal format.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        if not text:
            return ""

        # Escape special characters
        text = text.replace("\\", "\\\\")
        text = text.replace(";", "\\;")
        text = text.replace(",", "\\,")
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "")

        return text

    # =========================================================================
    # SESSION TEMPLATE METHODS
    # =========================================================================

    def create_session_template(
        self,
        name: str,
        frequency: str,
        day_of_week: int = None,
        time_of_day: str = None,
        duration_minutes: int = 120,
        default_location: str = None,
        default_meeting_link: str = None,
        default_chair_id: int = None,
        default_secretary_id: int = None,
        default_members: List[int] = None,
        created_by_id: int = None,
    ) -> Dict[str, Any]:
        """
        Create a recurring session template.

        Args:
            name: Template name
            frequency: weekly, biweekly, monthly
            day_of_week: 0=Monday, 6=Sunday
            time_of_day: Time in HH:MM format
            duration_minutes: Session duration
            default_location: Default location
            default_meeting_link: Default meeting link
            default_chair_id: Default chair user ID
            default_secretary_id: Default secretary user ID
            default_members: Default member user IDs
            created_by_id: Creator user ID

        Returns:
            Created template details
        """
        from datetime import time as dt_time

        # Parse time
        session_time = None
        if time_of_day:
            parts = time_of_day.split(":")
            session_time = dt_time(int(parts[0]), int(parts[1]))

        template = ARBSessionTemplate(
            name=name,
            frequency=frequency,
            day_of_week=day_of_week,
            time_of_day=session_time,
            duration_minutes=duration_minutes,
            default_location=default_location,
            default_meeting_link=default_meeting_link,
            default_chair_id=default_chair_id,
            default_secretary_id=default_secretary_id,
            default_members=default_members,
            is_active=True,
            created_by_id=created_by_id,
        )

        db.session.add(template)
        db.session.commit()

        # Calculate next session date
        next_date = self._calculate_next_session_date(template)
        if next_date:
            template.next_scheduled_date = next_date
            db.session.commit()

        logger.info(f"Created session template: {name}")

        return {
            "success": True,
            "template_id": template.id,
            "name": template.name,
            "frequency": template.frequency,
            "next_scheduled_date": next_date.isoformat() if next_date else None,
        }

    def generate_session_from_template(
        self,
        template_id: int,
        session_date: datetime = None,
    ) -> Optional[ARBSession]:
        """
        Generate a session from a template.

        Args:
            template_id: Template ID
            session_date: Optional override for session date

        Returns:
            Created ARBSession or None
        """
        template = db.session.get(ARBSessionTemplate, template_id)
        if not template:
            return None

        # Use provided date or calculate next date
        scheduled_date = session_date or self._calculate_next_session_date(template)

        if not scheduled_date:
            return None

        # Generate session number
        session_number = ARBSession.generate_session_number()

        session = ARBSession(
            session_number=session_number,
            session_type="regular",
            status="scheduled",
            scheduled_date=scheduled_date,
            duration_minutes=template.duration_minutes,
            location=template.default_location,
            meeting_link=template.default_meeting_link,
            chair_id=template.default_chair_id,
            secretary_id=template.default_secretary_id,
            attendees=template.default_members,
        )

        db.session.add(session)

        # Update template
        template.last_generated_at = datetime.utcnow()
        template.next_scheduled_date = self._calculate_next_session_date(
            template, after_date=scheduled_date
        )

        db.session.commit()

        logger.info(f"Generated session {session_number} from template {template.name}")

        return session

    def _calculate_next_session_date(
        self,
        template: ARBSessionTemplate,
        after_date: datetime = None,
    ) -> Optional[datetime]:
        """
        Calculate the next session date based on template.

        Args:
            template: Session template
            after_date: Calculate date after this date

        Returns:
            Next session datetime
        """
        base_date = after_date or datetime.utcnow()

        if template.day_of_week is None:
            return None

        # Find next occurrence of the day of week
        days_ahead = template.day_of_week - base_date.weekday()
        if days_ahead <= 0:
            # Adjust for frequency
            if template.frequency == "weekly":
                days_ahead += 7
            elif template.frequency == "biweekly":
                days_ahead += 14
            elif template.frequency == "monthly":
                days_ahead += 28  # Approximate

        next_date = base_date + timedelta(days=days_ahead)

        # Set time
        if template.time_of_day:
            next_date = next_date.replace(
                hour=template.time_of_day.hour,
                minute=template.time_of_day.minute,
                second=0,
                microsecond=0,
            )
        else:
            next_date = next_date.replace(hour=10, minute=0, second=0, microsecond=0)

        return next_date

    def list_session_templates(
        self,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List all session templates.

        Args:
            active_only: Only return active templates

        Returns:
            List of template details
        """
        query = ARBSessionTemplate.query
        if active_only:
            query = query.filter(ARBSessionTemplate.is_active == True)

        templates = query.order_by(ARBSessionTemplate.name).all()

        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "frequency": t.frequency,
                "day_of_week": t.day_of_week,
                "time_of_day": t.time_of_day.strftime("%H:%M") if t.time_of_day else None,
                "duration_minutes": t.duration_minutes,
                "default_location": t.default_location,
                "is_active": t.is_active,
                "last_generated_at": t.last_generated_at.isoformat()
                if t.last_generated_at
                else None,
                "next_scheduled_date": t.next_scheduled_date.isoformat()
                if t.next_scheduled_date
                else None,
            }
            for t in templates
        ]


# Create singleton instance
arb_calendar_service = ARBCalendarService()
