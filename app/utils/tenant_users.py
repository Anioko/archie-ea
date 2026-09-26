"""Look up a user by id, but only inside one organisation.

``User`` carries an ``organization_id`` column but no ``TenantMixin``, so the ORM tenant
filter does not apply to it. A lookup such as ``db.session.get(User, user_id)`` with an id
that came from a request or from stored JSON therefore returns a user of ANY organisation.
Use this wherever a user is resolved from such an id (to show a name, an e-mail, an
assignee) so the organisation check cannot be forgotten.
"""

from __future__ import annotations

from typing import Optional

from app.extensions import db


def user_in_org(user_id, org_id) -> Optional[object]:
    """The user with ``user_id`` who belongs to ``org_id``, else ``None``.

    Fails closed: a missing organisation, a non-numeric id or a user of another
    organisation all return ``None``.
    """
    from app.models.user import User

    if user_id in (None, "") or org_id is None:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.execute(
        db.select(User).where(User.id == user_id).where(User.organization_id == org_id)
    ).scalar_one_or_none()
