"""
Template utilities for Flask application
"""

import re

from markupsafe import Markup, escape


# ── Error humanization ──────────────────────────────────────────────
WORKFLOW_ERROR_PATTERNS = {
    'database': (
        ['sqlalchemy', 'integrityerror', 'operationalerror', 'databaseerror',
         'psycopg', 'sqlite'],
        "Database operation failed during workflow execution.",
    ),
    'validation': (
        ['valueerror', 'typeerror', 'keyerror', 'validation', 'missing required',
         'invalid'],
        "Invalid input encountered during workflow execution.",
    ),
    'file': (
        ['filenotfounderror', 'ioerror', 'csv', 'parse error', 'encoding'],
        "File processing failed during workflow execution.",
    ),
    'network': (
        ['connectionerror', 'timeouterror', 'network', 'unreachable'],
        "Network operation failed during workflow execution.",
    ),
    'permission': (
        ['permissionerror', 'access denied', 'forbidden', 'unauthorized'],
        "Access denied during workflow execution.",
    ),
}

_EXCEPTION_MARKERS = re.compile(
    r'Traceback|Error\b|Exception\b|^\w+Error:|^\w+Exception:',
    re.MULTILINE,
)


def humanize_error(error_msg):
    """Convert raw error messages into user-friendly HTML.

    - User-authored messages (rejections, cancellations) pass through unchanged.
    - Technical exceptions get a friendly summary with collapsible raw details.
    """
    if not error_msg:
        return Markup('')

    msg = str(error_msg)

    # Pass-through: user-authored messages
    if msg.startswith('Rejected by ') or msg.startswith('Cancelled by '):
        return Markup(escape(msg))

    # Check for technical markers
    lower = msg.lower()
    if not _EXCEPTION_MARKERS.search(msg):
        # No exception patterns — likely already human-friendly
        return Markup(escape(msg))

    # Classify the error
    friendly = "An unexpected error occurred during workflow execution."
    for _category, (keywords, summary) in WORKFLOW_ERROR_PATTERNS.items():
        if any(kw in lower for kw in keywords):
            friendly = summary
            break

    escaped_raw = escape(msg)
    return Markup(
        f'<span class="block">{escape(friendly)}'
        f' You can retry or contact support.</span>'
        f'<details class="mt-2 text-xs">'
        f'<summary class="cursor-pointer text-destructive/60 '
        f'hover:text-destructive/80">Technical details</summary>'
        f'<pre class="mt-1 p-2 rounded bg-muted text-muted-foreground '
        f'overflow-x-auto whitespace-pre-wrap break-words text-[11px]">'
        f'{escaped_raw}</pre></details>'
    )


def register_template_utils(app):
    """Register template utilities with Flask app."""
    _register(app)


def _register(app):
    """Inline registration of core template utilities."""
    from flask import url_for

    @app.template_test()
    def equalto(value, other):
        return value == other

    @app.template_global()
    def is_hidden_field(field):
        from wtforms.fields import HiddenField
        return isinstance(field, HiddenField)

    import builtins as _builtins

    @app.template_global("getattr")
    def template_getattr(obj, name, default=None):
        if obj is None:
            return default
        try:
            return _builtins.getattr(obj, name, default)
        except (AttributeError, TypeError):
            return default

    @app.template_filter("safe_attr")
    def safe_attr_filter(obj, attr_name, default=None):
        if obj is None:
            return default
        try:
            return _builtins.getattr(obj, attr_name, default)
        except (AttributeError, TypeError):
            return default

    def index_for_role(role):
        return url_for(role.index)

    app.add_template_global(index_for_role)

    # ── S2-01: i18n formatting filters ─────────────────────────────
    @app.template_filter("format_currency")
    def format_currency_filter(value, currency=None):
        """Format a number as locale-aware currency.

        Usage: {{ 1234.56|format_currency }}
               {{ 1234.56|format_currency('EUR') }}

        Falls back to CurrencyConfig if no currency specified,
        then to plain formatting if Flask-Babel unavailable.
        """
        if value is None:
            return ""
        try:
            from flask_babel import format_currency as babel_fmt

            if not currency:
                try:
                    from config import CurrencyConfig
                    currency = CurrencyConfig.get_currency_config().get("code", "USD")
                except Exception:
                    currency = "USD"
            return babel_fmt(value, currency)
        except ImportError:
            # Fallback without Babel
            try:
                from config import CurrencyConfig
                symbol = CurrencyConfig.get_currency_config().get("symbol", "$")
            except Exception:
                symbol = "$"
            return f"{symbol}{value:,.2f}"

    @app.template_filter("format_datetime")
    def format_datetime_filter(value, fmt="medium"):
        """Format a datetime as locale-aware string.

        Usage: {{ item.created_at|format_datetime }}
               {{ item.created_at|format_datetime('short') }}
               {{ item.created_at|format_datetime('yyyy-MM-dd HH:mm') }}

        Falls back to strftime if Flask-Babel unavailable.
        """
        if value is None:
            return ""
        try:
            from flask_babel import format_datetime as babel_fmt
            return babel_fmt(value, fmt)
        except ImportError:
            try:
                if fmt == "short":
                    return value.strftime("%m/%d/%y %H:%M")
                elif fmt == "medium":
                    return value.strftime("%b %d, %Y %H:%M")
                elif fmt == "long":
                    return value.strftime("%B %d, %Y %H:%M:%S")
                elif fmt == "full":
                    return value.strftime("%A, %B %d, %Y %H:%M:%S %Z")
                else:
                    return value.strftime(str(fmt))
            except (AttributeError, ValueError):
                return str(value)

    @app.template_filter("format_number")
    def format_number_filter(value, decimals=None):
        """Format a number with locale-aware grouping.

        Usage: {{ 1234567|format_number }}
               {{ 3.14159|format_number(2) }}
        """
        if value is None:
            return ""
        try:
            from flask_babel import format_decimal
            if decimals is not None:
                fmt = f"#,##0.{'0' * decimals}"
                return format_decimal(value, format=fmt)
            return format_decimal(value)
        except ImportError:
            if decimals is not None:
                return f"{value:,.{decimals}f}"
            if isinstance(value, float):
                return f"{value:,.2f}"
            return f"{value:,}"

    @app.template_filter("format_percent")
    def format_percent_filter(value, decimals=1):
        """Format a decimal as locale-aware percentage.

        Usage: {{ 0.85|format_percent }}     → 85.0%
               {{ 0.85|format_percent(0) }}  → 85%
        """
        if value is None:
            return ""
        try:
            from flask_babel import format_percent as babel_pct
            return babel_pct(value)
        except ImportError:
            return f"{value * 100:,.{decimals}f}%"
