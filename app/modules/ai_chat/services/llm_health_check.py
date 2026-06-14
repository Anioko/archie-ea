"""
LLM Health Check Service

Validates LLM provider configuration at application startup.

This module provides startup validation to detect missing or misconfigured
LLM providers before users encounter errors. If no provider is configured,
AI features are disabled gracefully instead of failing with 500 errors.

Usage:
    from app.services.llm_health_check import validate_llm_config

    # During app initialization
    llm_status = validate_llm_config()
    app.config['AI_FEATURES_ENABLED'] = llm_status['configured']
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def validate_llm_config() -> Dict[str, Optional[str]]:
    """
    Validate LLM provider configuration at startup.

    Checks if at least one LLM provider is configured and enabled in the
    APISettings table. Uses FeatureFlagService to leverage existing
    provider detection logic.

    Returns:
        dict: Configuration status with keys:
            - configured (bool): True if at least one provider is configured
            - provider (str|None): Name of configured provider (e.g., 'openai')
            - model (str|None): Name of default model (e.g., 'gpt-4')
            - message (str): Human-readable status message

    Examples:
        >>> result = validate_llm_config()
        >>> result['configured']
        True
        >>> result['provider']
        'openai'
        >>> result['model']
        'gpt-4'

        >>> result = validate_llm_config()  # No provider configured
        >>> result['configured']
        False
        >>> result['message']
        'No LLM provider configured. AI features will be disabled.'
    """
    try:
        # Import here to avoid circular dependency during app initialization
        from flask import has_app_context
        from app.services.feature_flag_service import FeatureFlagService

        # Check if we're in an app context (needed for database queries)
        if not has_app_context():
            logger.warning(
                "validate_llm_config() called outside app context. "
                "Cannot check LLM configuration."
            )
            return {
                'configured': False,
                'provider': None,
                'model': None,
                'message': 'LLM validation skipped (no app context)'
            }

        # Use existing provider detection logic
        info = FeatureFlagService.get_configured_provider_info()

        if info and info.get('configured'):
            provider = info.get('provider')
            model = info.get('model')

            logger.info(
                f"LLM provider configured: {provider}/{model}"
            )

            return {
                'configured': True,
                'provider': provider,
                'model': model,
                'message': f"LLM configured: {provider}/{model}"
            }
        else:
            logger.warning(
                "No LLM provider configured. AI features will be disabled. "
                "Configure a provider in APISettings table to enable AI features."
            )

            return {
                'configured': False,
                'provider': None,
                'model': None,
                'message': 'No LLM provider configured. AI features will be disabled.'
            }

    except Exception as e:
        # Catch all exceptions to prevent app startup failure
        logger.error(
            f"Error validating LLM configuration: {e}. "
            "AI features will be disabled."
        )

        return {
            'configured': False,
            'provider': None,
            'model': None,
            'message': f'LLM validation error: {str(e)}'
        }


def is_ai_available() -> bool:
    """
    Quick check if AI features are available.

    This is a convenience function that wraps validate_llm_config()
    and returns only the boolean status.

    Returns:
        bool: True if AI features are configured and available

    Examples:
        >>> is_ai_available()
        True
    """
    result = validate_llm_config()
    return result.get('configured', False)
