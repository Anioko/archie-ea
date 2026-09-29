"""Legacy path for sidebar menu audit logging.

The v2 module (app/modules/admin/v2/services/sidebar_menu_audit_log_v2.py) is the one live at boot
with the default guardrail flags. This legacy copy is only reached when the admin guardrail flag is
switched off, and duplicated the same current_user.username bug fixed in the v2 module (PR 263) --
User has no username attribute. Rather than fix the same bug twice, this re-exports the one
implementation.
"""

from app.modules.admin.v2.services.sidebar_menu_audit_log_v2 import SidebarMenuAuditLog  # noqa: F401
