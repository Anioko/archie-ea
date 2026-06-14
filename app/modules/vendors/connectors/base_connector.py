# app/modules/vendors/connectors/base_connector.py
"""Abstract base class for cloud pricing API connectors."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a connector sync operation."""
    provider: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    services_synced: int = 0
    pricing_rows_created: int = 0
    pricing_rows_updated: int = 0
    errors: list = field(default_factory=list)
    healthy: bool = True

    def finish(self):
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "services_synced": self.services_synced,
            "pricing_rows_created": self.pricing_rows_created,
            "pricing_rows_updated": self.pricing_rows_updated,
            "errors": self.errors[:10],
            "healthy": self.healthy,
        }


class BaseCloudPricingConnector(ABC):
    """Abstract base for cloud pricing connectors (AWS, Azure, GCP)."""

    @abstractmethod
    def sync(self, service_filter: Optional[str] = None) -> SyncResult:
        """Fetch pricing from provider API, write to VendorProductPricing."""

    @abstractmethod
    def health_check(self) -> bool:
        """Validate API credentials and connectivity."""

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (aws, azure, gcp)."""
