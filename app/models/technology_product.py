"""Small compatibility placeholder for `TechnologyProduct`.

Some modules import `TechnologyProduct` from `app.models`. The canonical
codebase doesn't define a dedicated `TechnologyProduct` ORM in a flat module
path, so provide a lightweight alias to avoid import-time errors during test
collection. This is intentionally minimal and avoids creating DB objects.
"""


class TechnologyProduct:
    """Lightweight placeholder for import-time compatibility."""

    def __init__(self, *args, **kwargs):
        self.id = kwargs.get("id")
        self.name = kwargs.get("name")

    def __repr__(self):
        return f"<TechnologyProduct name={getattr(self, 'name', None)}>"


__all__ = ["TechnologyProduct"]
