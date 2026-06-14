"""Dashboard v2 adapter for options analysis engine."""

import importlib

_options_module = importlib.import_module("app.services.options_analysis_engine")
AnalysisOption = _options_module.AnalysisOption
get_options_analysis_engine = _options_module.get_options_analysis_engine

__all__ = ["AnalysisOption", "get_options_analysis_engine"]
