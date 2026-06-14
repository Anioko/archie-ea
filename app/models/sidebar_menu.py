"""Sidebar menu item toggle management model."""
from app.extensions import db


class SidebarMenuItem(db.Model):
    """Tracks enabled/disabled state of sidebar menu items."""

    __tablename__ = "sidebar_menu_items"

    id = db.Column(db.Integer, primary_key=True)

    # Hierarchical menu structure
    key = db.Column(
        db.String(100), unique=True, nullable=False, index=True
    )  # e.g., 'app.vendors.dashboard'
    label = db.Column(db.String(200), nullable=False)  # e.g., 'Vendor Dashboard'
    section = db.Column(db.String(100), nullable=False, index=True)  # e.g., 'Application'
    subsection = db.Column(db.String(100), nullable=True)  # e.g., 'Vendor Management'
    level = db.Column(db.Integer, default=1)  # 1=main, 2=sub, 3=sub-sub

    # Control
    is_enabled = db.Column(db.Boolean, default=True, index=True)
    order = db.Column(db.Integer, default=0)  # Sort order within section
    
    # Role-based access control (comma-separated roles or null for all)
    # e.g., "admin,architect" means only admin and architect roles can see this
    required_roles = db.Column(db.String(255), nullable=True)  # null = visible to all

    # Metadata
    icon = db.Column(db.String(50), nullable=True)  # lucide icon name
    route = db.Column(db.String(200), nullable=True)  # Flask route endpoint
    description = db.Column(db.Text, nullable=True)
    
    # Breadcrumb support
    breadcrumb_label = db.Column(db.String(100), nullable=True)  # Override label in breadcrumb
    show_in_breadcrumb = db.Column(db.Boolean, default=True)  # Include in breadcrumb trail

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "section": self.section,
            "subsection": self.subsection,
            "level": self.level,
            "is_enabled": self.is_enabled,
            "order": self.order,
            "icon": self.icon,
            "route": self.route,
            "description": self.description,
            "required_roles": self.required_roles,
            "breadcrumb_label": self.breadcrumb_label,
            "show_in_breadcrumb": self.show_in_breadcrumb,
        }
    
    def get_breadcrumb_trail(self):
        """Get breadcrumb trail for this menu item.
        
        Returns list of dicts: [section, subsection?, this_item]
        """
        if not self.show_in_breadcrumb:
            return []
        
        trail = []
        
        # Add section
        trail.append({
            "label": self.section,
            "is_current": False,
        })
        
        # Add subsection if exists
        if self.subsection:
            trail.append({
                "label": self.subsection,
                "is_current": False,
            })
        
        # Add this item as current
        trail.append({
            "label": self.breadcrumb_label or self.label,
            "route": self.route,
            "is_current": True,
        })
        
        return trail
    
    def is_visible_to_user(self, user):
        """Check if menu item is visible to user based on role and enabled status."""
        if not self.is_enabled:
            return False
        
        if not user:
            return False
            
        # If no role restriction, show to all authenticated users
        if not self.required_roles:
            return True
        
        # Check if user has any of the required roles
        required = set(r.strip().lower() for r in self.required_roles.split(','))
        user_roles = set(r.lower() for r in getattr(user, 'roles', []))
        
        return bool(required & user_roles)

    def __repr__(self):
        status = "✓" if self.is_enabled else "✗"
        return f"<SidebarMenuItem {status} {self.key}>"
