"""
API Marketplace Integration Service

Provides hooks and infrastructure for integrating with API marketplaces:
- OAuth 2.0 provider
- API key management
- Rate limiting
- Usage tracking
- Billing webhooks
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from flask import current_app

from app import db

logger = logging.getLogger(__name__)


class APIKey:
    """Represents an API key for marketplace integration."""

    def __init__(self, key_id: str, key_secret: str, organization_id: int, scopes: List[str]):
        self.key_id = key_id
        self.key_secret = key_secret
        self.organization_id = organization_id
        self.scopes = scopes
        self.created_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(days=365)
        self.is_active = True
        self.usage_count = 0
        self.last_used_at = None


class APIMarketplaceIntegration:
    """
    Main service for API marketplace integration.

    Features:
    - API key generation and validation
    - OAuth 2.0 provider
    - Rate limiting
    - Usage tracking
    - Billing integration
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._api_keys = {}  # In-memory storage (would use database in production)
        self._usage_stats = {}

    def generate_api_key(self, organization_id: int, scopes: List[str] = None) -> Dict[str, str]:
        """
        Generate a new API key.

        Args:
            organization_id: Organization ID
            scopes: List of API scopes (e.g., ['read:applications', 'write:capabilities'])

        Returns:
            Dictionary with key_id and key_secret
        """
        if scopes is None:
            scopes = ["read:*"]  # Default read-only access

        # Generate key ID and secret
        key_id = f"mk_{secrets.token_urlsafe(16)}"
        key_secret = secrets.token_urlsafe(32)

        # Hash the secret for storage
        secret_hash = hashlib.sha256(key_secret.encode()).hexdigest()

        # Create API key
        api_key = APIKey(key_id, secret_hash, organization_id, scopes)
        self._api_keys[key_id] = api_key

        self.logger.info(f"Generated API key {key_id} for organization {organization_id}")

        return {
            "key_id": key_id,
            "key_secret": key_secret,  # Only return unhashed secret once
            "scopes": scopes,
            "expires_at": api_key.expires_at.isoformat(),
        }

    def validate_api_key(self, key_id: str, key_secret: str) -> Optional[APIKey]:
        """
        Validate an API key.

        Args:
            key_id: API key ID
            key_secret: API key secret

        Returns:
            APIKey object if valid, None otherwise
        """
        api_key = self._api_keys.get(key_id)

        if not api_key:
            return None

        # Check if key is active
        if not api_key.is_active:
            self.logger.warning(f"API key {key_id} is inactive")
            return None

        # Check expiration
        if api_key.expires_at < datetime.utcnow():
            self.logger.warning(f"API key {key_id} is expired")
            return None

        # Validate secret
        secret_hash = hashlib.sha256(key_secret.encode()).hexdigest()
        if api_key.key_secret != secret_hash:
            self.logger.warning(f"Invalid secret for API key {key_id}")
            return None

        # Update usage stats
        api_key.usage_count += 1
        api_key.last_used_at = datetime.utcnow()

        return api_key

    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: API key ID

        Returns:
            True if revoked, False if not found
        """
        api_key = self._api_keys.get(key_id)

        if not api_key:
            return False

        api_key.is_active = False
        self.logger.info(f"Revoked API key {key_id}")

        return True

    def check_rate_limit(self, key_id: str) -> Dict[str, Any]:
        """
        Check rate limit for an API key.

        Args:
            key_id: API key ID

        Returns:
            Rate limit status
        """
        # Simple rate limiting (would use Redis in production)
        if key_id not in self._usage_stats:
            self._usage_stats[key_id] = {"requests": 0, "window_start": datetime.utcnow()}

        stats = self._usage_stats[key_id]

        # Check if window has expired (1 hour window)
        if (datetime.utcnow() - stats["window_start"]).seconds > 3600:
            stats["requests"] = 0
            stats["window_start"] = datetime.utcnow()

        # Increment counter
        stats["requests"] += 1

        # Rate limits
        rate_limit = 1000  # requests per hour
        remaining = max(0, rate_limit - stats["requests"])

        return {
            "limit": rate_limit,
            "remaining": remaining,
            "reset_at": (stats["window_start"] + timedelta(hours=1)).isoformat(),
            "rate_limited": stats["requests"] > rate_limit,
        }

    def track_usage(self, key_id: str, endpoint: str, method: str, response_code: int):
        """
        Track API usage for billing.

        Args:
            key_id: API key ID
            endpoint: API endpoint
            method: HTTP method
            response_code: Response status code
        """
        if key_id not in self._usage_stats:
            self._usage_stats[key_id] = {"total_requests": 0, "by_endpoint": {}, "by_status": {}}

        stats = self._usage_stats[key_id]
        stats["total_requests"] += 1

        # Track by endpoint
        if endpoint not in stats["by_endpoint"]:
            stats["by_endpoint"][endpoint] = 0
        stats["by_endpoint"][endpoint] += 1

        # Track by status code
        status_group = f"{response_code // 100}xx"
        if status_group not in stats["by_status"]:
            stats["by_status"][status_group] = 0
        stats["by_status"][status_group] += 1

    def get_usage_stats(self, key_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for an API key.

        Args:
            key_id: API key ID

        Returns:
            Usage statistics
        """
        stats = self._usage_stats.get(key_id, {})
        api_key = self._api_keys.get(key_id)

        return {
            "key_id": key_id,
            "total_requests": stats.get("total_requests", 0),
            "by_endpoint": stats.get("by_endpoint", {}),
            "by_status": stats.get("by_status", {}),
            "last_used_at": api_key.last_used_at.isoformat()
            if api_key and api_key.last_used_at
            else None,
        }

    def generate_oauth_token(
        self, client_id: str, client_secret: str, scopes: List[str]
    ) -> Dict[str, Any]:
        """
        Generate OAuth 2.0 access token.

        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            scopes: Requested scopes

        Returns:
            OAuth token response
        """
        # Validate client credentials
        # (Would validate against database in production)

        # Generate JWT token
        payload = {
            "sub": client_id,
            "scopes": scopes,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
        }

        secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": " ".join(scopes),
        }

    def validate_oauth_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate OAuth 2.0 token.

        Args:
            token: JWT token

        Returns:
            Token payload if valid, None otherwise
        """
        try:
            secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None

    def calculate_billing(self, key_id: str, billing_period: str = "month") -> Dict[str, Any]:
        """
        Calculate billing for an API key.

        Args:
            key_id: API key ID
            billing_period: Billing period ('month', 'day')

        Returns:
            Billing information
        """
        stats = self.get_usage_stats(key_id)

        # Pricing tiers (example)
        base_price = 0  # Free tier
        price_per_1k_requests = 0.01

        total_requests = stats["total_requests"]

        # Calculate cost
        if total_requests <= 10000:
            cost = base_price
        else:
            billable_requests = total_requests - 10000
            cost = base_price + (billable_requests / 1000) * price_per_1k_requests

        return {
            "key_id": key_id,
            "billing_period": billing_period,
            "total_requests": total_requests,
            "free_tier_requests": min(total_requests, 10000),
            "billable_requests": max(0, total_requests - 10000),
            "cost_usd": round(cost, 2),
            "breakdown": {"base_price": base_price, "usage_charges": round(cost - base_price, 2)},
        }

    def get_marketplace_info(self) -> Dict[str, Any]:
        """
        Get marketplace integration information.

        Returns:
            Marketplace configuration and endpoints
        """
        base_url = current_app.config.get("API_BASE_URL", "https://api.example.com")

        return {
            "name": "Flask-Shadcn Enterprise API",
            "version": "1.0.0",
            "base_url": base_url,
            "authentication": {
                "methods": ["api_key", "oauth2"],
                "oauth2": {
                    "authorization_url": f"{base_url}/oauth/authorize",
                    "token_url": f"{base_url}/oauth/token",
                    "scopes": {
                        "read:applications": "Read application data",
                        "write:applications": "Create and update applications",
                        "read:capabilities": "Read capability data",
                        "write:capabilities": "Create and update capabilities",
                        "read:vendors": "Read vendor data",
                        "write:vendors": "Create and update vendors",
                    },
                },
            },
            "rate_limits": {
                "default": {"requests_per_hour": 1000, "burst": 100},
                "premium": {"requests_per_hour": 10000, "burst": 500},
            },
            "pricing": {
                "free_tier": {"requests_per_month": 10000, "price": 0},
                "pay_as_you_go": {"price_per_1k_requests": 0.01},
                "premium": {"requests_per_month": 1000000, "price_per_month": 99},
            },
            "documentation_url": f"{base_url}/docs",
            "support_email": "api-support@example.com",
        }


# Singleton instance
_marketplace_integration = None


def get_marketplace_integration() -> APIMarketplaceIntegration:
    """Get or create the marketplace integration instance."""
    global _marketplace_integration

    if _marketplace_integration is None:
        _marketplace_integration = APIMarketplaceIntegration()

    return _marketplace_integration
