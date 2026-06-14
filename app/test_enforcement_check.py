"""Test file to verify enforcement works"""

# This will trigger multiple violations:
import unused_module  # Dead code: unused import


def calculate_cost():
    """Calculate cost with magic number"""
    return 5000  # Fabricated values: magic number in financial context


def get_user_data(user):
    """Unsafe ORM access"""
    if hasattr(user, "name"):  # Model safety: hasattr on ORM
        return user.name
    return None
