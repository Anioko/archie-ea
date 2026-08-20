"""Legacy ``app.ai_chat`` package.

The flat blueprints that lived here (``ai_chat``, ``entity_matching``,
``business_output``, and the ``data_interaction`` stub) were never registered and
are superseded by ``app.modules.ai_chat``. They were deleted; only
``element_field_mapper`` remains, which ``app.modules.ai_chat`` still imports.
"""
