# app/modules/vendors/connectors/aws_connector.py
"""AWS Price List API connector for cloud pricing sync."""
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization, VendorProduct, VendorProductPricing, VendorProductCapability,
)
from app.modules.vendors.connectors.base_connector import BaseCloudPricingConnector, SyncResult
from app.modules.vendors.connectors.capability_mapping import AWS_CAPABILITY_MAP

logger = logging.getLogger(__name__)

# AWS Price List API base URL (public, no auth required)
AWS_PRICING_API = "https://pricing.us-east-1.amazonaws.com"
AWS_PRICING_INDEX = f"{AWS_PRICING_API}/offers/v1.0/aws/index.json"

# Region-specific offer URL — returns only prices for one region (~5-50 MB vs 600 MB for global).
# Format: /offers/v1.0/aws/{service}/current/{region}/index.json
AWS_REGION_OFFER_URL = f"{AWS_PRICING_API}/offers/v1.0/aws/{{service}}/current/{{region}}/index.json"

# Hard ceiling: refuse to parse any response larger than this.
_MAX_RESPONSE_BYTES = 200 * 1024 * 1024  # 200 MB

# Request timeout for large but filtered offer files.
_REQUEST_TIMEOUT_SECONDS = 300

# Top services to sync (by service code)
DEFAULT_SERVICES = [
    "AmazonEC2", "AmazonRDS", "AmazonS3", "AWSLambda", "AmazonECS",
    "AmazonEKS", "AmazonDynamoDB", "AmazonElastiCache", "AmazonSES",
    "AmazonSQS", "AmazonSNS", "AmazonRedshift", "AmazonCloudFront",
    "AmazonRoute53", "AmazonSageMaker", "AmazonOpenSearchService",
    "AmazonAPIGateway", "AmazonCognito", "AmazonGuardDuty", "AmazonAurora",
]


class AWSPricingConnector(BaseCloudPricingConnector):
    """Syncs pricing from AWS Price List Bulk API.

    Uses region-specific offer files instead of the global index to avoid
    loading multi-hundred-megabyte payloads into memory.  Each region file
    covers only one AWS region and is typically 5-50 MB — safe to buffer in
    a production process.
    """

    def __init__(
        self,
        default_region: str = "eu-west-1",
        max_skus_per_service: int = 50,
    ):
        self.default_region = default_region
        self.max_skus_per_service = max_skus_per_service
        self._region_filter = self._get_region_location(default_region)

    def provider_name(self) -> str:
        return "aws"

    def health_check(self) -> bool:
        """Check if AWS Pricing API is reachable."""
        try:
            resp = requests.get(AWS_PRICING_INDEX, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"AWS pricing API health check failed: {e}")
            return False

    def sync(self, service_filter: Optional[str] = None) -> SyncResult:
        """Sync pricing for AWS services."""
        result = SyncResult(provider="aws")
        services = [service_filter] if service_filter else DEFAULT_SERVICES

        vendor = self._get_or_create_vendor()
        if not vendor:
            result.errors.append("Failed to get/create AWS vendor")
            result.healthy = False
            result.finish()
            return result

        for service_code in services:
            try:
                self._sync_service(service_code, vendor, result)
            except Exception as e:
                result.errors.append(f"{service_code}: {str(e)}")
                logger.error(f"Error syncing {service_code}: {e}")

        db.session.commit()
        result.finish()
        logger.info(
            f"AWS sync complete: {result.services_synced} services, "
            f"{result.pricing_rows_created} created, {result.pricing_rows_updated} updated"
        )
        return result

    def _fetch_region_offer(self, service_code: str) -> Optional[dict]:
        """Download the region-specific offer file for *service_code*.

        Returns the parsed JSON dict, or None on any error.  Guards against
        oversized responses by inspecting Content-Length before buffering.
        """
        url = AWS_REGION_OFFER_URL.format(
            service=service_code, region=self.default_region
        )
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS, stream=True)
        if resp.status_code != 200:
            logger.warning(
                f"AWS pricing: {service_code} region offer returned HTTP {resp.status_code}"
            )
            return None

        # Reject payloads that exceed our safety ceiling before buffering.
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_RESPONSE_BYTES:
            logger.error(
                f"AWS pricing: {service_code} offer file is "
                f"{int(content_length) // (1024*1024)} MB — exceeds "
                f"{_MAX_RESPONSE_BYTES // (1024*1024)} MB limit, skipping."
            )
            resp.close()
            return None

        # Buffer the (bounded) response and parse JSON.
        # Region-specific files are small enough that streaming chunk-by-chunk
        # and reassembling is equivalent — we still need the full dict for
        # random-access lookups into `products` and `terms`.
        data = resp.json()
        return data

    def _sync_service(
        self,
        service_code: str,
        vendor,
        result: SyncResult,
    ):
        """Sync a single AWS service's pricing using the region-specific offer file."""
        cap_name = AWS_CAPABILITY_MAP.get(service_code)
        if not cap_name:
            return

        data = self._fetch_region_offer(service_code)
        if data is None:
            result.errors.append(f"{service_code}: failed to fetch region offer")
            return

        products = data.get("products", {})
        terms = data.get("terms", {}).get("OnDemand", {})

        # Get or create product
        product = VendorProduct.query.filter_by(
            vendor_organization_id=vendor.id, name=service_code
        ).first()
        if not product:
            product = VendorProduct(
                vendor_organization_id=vendor.id,
                name=service_code,
                product_family_name="Cloud Infrastructure",
                deployment_model="cloud",
            )
            db.session.add(product)
            db.session.flush()

        # Extract representative pricing up to max_skus_per_service.
        # Region-specific files already filter by region, but the location
        # attribute check is retained as a safety net.
        skus_processed = 0
        for sku, product_info in products.items():
            if skus_processed >= self.max_skus_per_service:
                break

            attrs = product_info.get("attributes", {})
            location = attrs.get("location", "")
            if self._region_filter and self._region_filter not in location:
                continue

            sku_terms = terms.get(sku, {})
            for offer_id, offer in sku_terms.items():
                for dim_id, dim in offer.get("priceDimensions", {}).items():
                    price_str = dim.get("pricePerUnit", {}).get("USD", "0")
                    try:
                        hourly_price = float(price_str)
                    except ValueError:
                        continue
                    if hourly_price <= 0:
                        continue

                    annual_price = round(hourly_price * 8760, 2)
                    instance_type = attrs.get("instanceType", "default")
                    tier_name = f"OnDemand-{instance_type}"

                    existing = VendorProductPricing.query.filter_by(
                        product_id=product.id, tier_name=tier_name
                    ).first()
                    if existing:
                        existing.list_price_annual = annual_price
                        existing.data_source_type = "api_synced"
                        existing.last_verified_at = datetime.now(timezone.utc)
                        existing.source = "AWS Price List API"
                        result.pricing_rows_updated += 1
                    else:
                        pricing = VendorProductPricing(
                            product_id=product.id,
                            pricing_model="per_hour",
                            tier_name=tier_name,
                            list_price_annual=annual_price,
                            currency="USD",
                            source="AWS Price List API",
                            data_source_type="api_synced",
                            last_verified_at=datetime.now(timezone.utc),
                        )
                        db.session.add(pricing)
                        result.pricing_rows_created += 1

                    skus_processed += 1
                    # Only take first matching price dimension per SKU.
                    break
                break

        # Map capability
        cap = BusinessCapability.query.filter(
            db.func.lower(BusinessCapability.name) == cap_name.lower()
        ).first()
        if cap:
            existing_map = VendorProductCapability.query.filter_by(
                vendor_product_id=product.id, business_capability_id=cap.id
            ).first()
            if not existing_map:
                mapping = VendorProductCapability(
                    vendor_product_id=product.id,
                    business_capability_id=cap.id,
                    coverage_percentage=90.0,
                    data_source_type="api_synced",
                )
                db.session.add(mapping)

        result.services_synced += 1

    def _get_or_create_vendor(self):
        """Get or create AWS vendor organization."""
        vendor = VendorOrganization.query.filter_by(name="Amazon Web Services").first()
        if not vendor:
            vendor = VendorOrganization(
                name="Amazon Web Services",
                status="active",
                code="VEND-AWS",
                seed_source_id="seed-aws-connector",
                seeded_by="aws_connector",
            )
            db.session.add(vendor)
            db.session.flush()
        return vendor

    @staticmethod
    def _get_region_location(region_code: str) -> str:
        """Map AWS region code to pricing API location string."""
        region_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "EU (Ireland)",
            "eu-central-1": "EU (Frankfurt)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
        }
        return region_map.get(region_code, "EU (Ireland)")
