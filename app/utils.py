from flask import url_for
from wtforms.fields import Field
from wtforms.widgets import HiddenInput


def register_template_utils(app):
    """Register Jinja 2 helpers (called from __init__.py)."""

    @app.template_test()
    def equalto(value, other):
        return value == other

    @app.template_global()
    def is_hidden_field(field):
        from wtforms.fields import HiddenField

        return isinstance(field, HiddenField)

    # Add getattr as a global template function
    import builtins as _builtins

    @app.template_global("getattr")
    def template_getattr(obj, name, default=None):
        """Safe getattr function for templates"""
        if obj is None:
            return default
        try:
            return _builtins.getattr(obj, name, default)
        except (AttributeError, TypeError):
            return default

    # Add safe_attr as a filter for safe attribute access
    @app.template_filter("safe_attr")
    def safe_attr_filter(obj, attr_name, default=None):
        """Safely get attribute from object, returning default if not found"""
        if obj is None:
            return default
        try:
            import builtins as _builtins

            return _builtins.getattr(obj, attr_name, default)
        except (AttributeError, TypeError):
            return default

    app.add_template_global(index_for_role)


def index_for_role(role):
    return url_for(role.index)


class CustomSelectField(Field):
    widget = HiddenInput()

    def __init__(
        self, label="", validators=None, multiple=False, choices=[], allow_custom=True, **kwargs
    ):
        super(CustomSelectField, self).__init__(label, validators, **kwargs)
        self.multiple = multiple
        self.choices = choices
        self.allow_custom = allow_custom

    def _value(self):
        return str(self.data) if self.data is not None else ""

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = valuelist[1]
            self.raw_data = [valuelist[1]]
        else:
            self.data = ""
