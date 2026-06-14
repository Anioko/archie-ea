"""
CostEstimator — Estimate monthly AWS cloud costs from architecture spec.

Reads infrastructure configuration from ProductSpecBundle (database instance
class, replicas, messaging, networking) and produces a line-item cost breakdown
with documented assumptions.

Pricing data is approximate and based on us-east-1 on-demand rates (2025-Q4).
"""
import logging

logger = logging.getLogger(__name__)

# ── AWS Pricing Data (us-east-1, on-demand, 2025-Q4 approximate) ──────────

AWS_PRICING = {
    "compute": {
        # EKS pod costs (based on requested resources)
        "cpu_per_vcpu_hour": 0.0464,       # ~$33.5/month per vCPU
        "memory_per_gb_hour": 0.00511,     # ~$3.7/month per GB
    },
    "database": {
        "db.t3.micro": 12.41,
        "db.t3.small": 24.82,
        "db.t3.medium": 49.64,
        "db.t3.large": 99.28,
        "db.t4g.micro": 11.52,
        "db.t4g.small": 23.04,
        "db.t4g.medium": 46.08,
        "db.t4g.large": 92.16,
        "db.r6g.large": 131.40,
        "db.r6g.xlarge": 262.80,
        "db.m6g.large": 118.26,
        "db.m6g.xlarge": 236.52,
        "storage_per_gb": 0.115,
        "multi_az_multiplier": 2.0,
        "backup_per_gb": 0.095,
    },
    "networking": {
        "load_balancer": 16.20,            # ALB base cost
        "data_transfer_per_gb": 0.09,      # after first 1GB free
        "nat_gateway": 32.40,
    },
    "messaging": {
        "kafka_broker_hour": 0.21,         # MSK per broker
        "sqs_per_million_requests": 0.40,
    },
    "monitoring": {
        "cloudwatch_per_metric": 0.30,
        "cloudwatch_logs_per_gb": 0.50,
    },
}

# Hours in a month (730 = 365*24/12)
HOURS_PER_MONTH = 730

# Default assumptions
DEFAULT_DATA_TRANSFER_GB = 100
DEFAULT_LOG_VOLUME_GB = 10
DEFAULT_METRICS_COUNT = 20
DEFAULT_KAFKA_BROKERS = 3
DEFAULT_COST_WARNING_THRESHOLD = 500


class CostEstimator:
    """Estimate monthly cloud costs from a ProductSpecBundle or raw config."""

    def __init__(self, pricing=None, warning_threshold=DEFAULT_COST_WARNING_THRESHOLD):
        self.pricing = pricing or AWS_PRICING
        self.warning_threshold = warning_threshold

    def estimate(self, spec_bundle):
        """Calculate monthly cost estimate from a ProductSpecBundle.

        Args:
            spec_bundle: ProductSpecBundle with deployment, integrations, services.

        Returns:
            dict with total_monthly_usd, breakdown, assumptions, annual_usd,
            and optional warning if cost exceeds threshold.
        """
        breakdown = []
        assumptions = []

        # ── Compute (EKS pods) ──
        compute_items, compute_assumptions = self._estimate_compute(spec_bundle)
        breakdown.extend(compute_items)
        assumptions.extend(compute_assumptions)

        # ── Database (RDS) ──
        db_items, db_assumptions = self._estimate_database(spec_bundle)
        breakdown.extend(db_items)
        assumptions.extend(db_assumptions)

        # ── Networking ──
        services_count = len(getattr(spec_bundle, "services", []) or [])
        net_items, net_assumptions = self._estimate_networking(services_count)
        breakdown.extend(net_items)
        assumptions.extend(net_assumptions)

        # ── Messaging ──
        integrations = getattr(spec_bundle, "integrations", {}) or {}
        events = getattr(spec_bundle, "events", []) or []
        msg_items, msg_assumptions = self._estimate_messaging(integrations, events)
        breakdown.extend(msg_items)
        assumptions.extend(msg_assumptions)

        # ── Monitoring ──
        mon_items, mon_assumptions = self._estimate_monitoring(services_count)
        breakdown.extend(mon_items)
        assumptions.extend(mon_assumptions)

        # Aggregate
        total_monthly = sum(item["monthly_usd"] for item in breakdown)
        total_monthly = round(total_monthly, 2)
        annual = round(total_monthly * 12, 2)

        result = {
            "total_monthly_usd": total_monthly,
            "breakdown": breakdown,
            "assumptions": assumptions,
            "annual_usd": annual,
        }

        if total_monthly > self.warning_threshold:
            result["warning"] = (
                f"Estimated monthly cost (${total_monthly:,.2f}) exceeds "
                f"${self.warning_threshold:,.2f} threshold"
            )

        return result

    def estimate_from_config(self, config):
        """Calculate cost from a raw config dict (for API use without full bundle).

        Args:
            config: dict with optional keys:
                - database: {instance_class, storage_gb, multi_az, backup_days}
                - compute: {replicas, cpu_millicores, memory_mb}
                - services_count: int
                - has_kafka: bool
                - has_sqs: bool

        Returns:
            Same format as estimate().
        """
        breakdown = []
        assumptions = []

        # Compute
        compute_cfg = config.get("compute", {})
        if compute_cfg:
            items, asms = self._estimate_compute_from_config(compute_cfg)
            breakdown.extend(items)
            assumptions.extend(asms)

        # Database
        db_cfg = config.get("database", {})
        if db_cfg:
            items, asms = self._estimate_database_from_config(db_cfg)
            breakdown.extend(items)
            assumptions.extend(asms)

        # Networking
        svc_count = config.get("services_count", 1)
        items, asms = self._estimate_networking(svc_count)
        breakdown.extend(items)
        assumptions.extend(asms)

        # Messaging
        if config.get("has_kafka"):
            items, asms = self._estimate_kafka()
            breakdown.extend(items)
            assumptions.extend(asms)
        if config.get("has_sqs"):
            items, asms = self._estimate_sqs()
            breakdown.extend(items)
            assumptions.extend(asms)

        # Monitoring
        items, asms = self._estimate_monitoring(svc_count)
        breakdown.extend(items)
        assumptions.extend(asms)

        total_monthly = round(sum(i["monthly_usd"] for i in breakdown), 2)
        annual = round(total_monthly * 12, 2)

        result = {
            "total_monthly_usd": total_monthly,
            "breakdown": breakdown,
            "assumptions": assumptions,
            "annual_usd": annual,
        }

        if total_monthly > self.warning_threshold:
            result["warning"] = (
                f"Estimated monthly cost (${total_monthly:,.2f}) exceeds "
                f"${self.warning_threshold:,.2f} threshold"
            )

        return result

    # ── Private estimation methods ────────────────────────────────────────

    def _estimate_compute(self, spec_bundle):
        """Estimate compute costs from bundle deployment spec."""
        deployment = getattr(spec_bundle, "deployment", None)
        if not deployment:
            # Fallback: assume 2 replicas at 256MB each
            return self._estimate_compute_from_config({
                "replicas": 2, "cpu_millicores": 250, "memory_mb": 256,
            })

        dep = deployment if isinstance(deployment, dict) else vars(deployment)
        scaling = dep.get("scaling", {})
        replicas = scaling.get("min_replicas", 2)

        # Default resource requests per pod
        cpu_m = 250   # millicores
        memory_mb = 256

        return self._estimate_compute_from_config({
            "replicas": replicas,
            "cpu_millicores": cpu_m,
            "memory_mb": memory_mb,
        })

    def _estimate_compute_from_config(self, cfg):
        replicas = cfg.get("replicas", 2)
        cpu_m = cfg.get("cpu_millicores", 250)
        memory_mb = cfg.get("memory_mb", 256)

        cpu_vcpu = cpu_m / 1000.0
        memory_gb = memory_mb / 1024.0

        pricing = self.pricing["compute"]
        cpu_cost = cpu_vcpu * pricing["cpu_per_vcpu_hour"] * HOURS_PER_MONTH * replicas
        mem_cost = memory_gb * pricing["memory_per_gb_hour"] * HOURS_PER_MONTH * replicas
        total = round(cpu_cost + mem_cost, 2)

        items = [{
            "category": "Compute",
            "service": f"EKS Pods ({replicas} replicas x {cpu_m}m CPU / {memory_mb}MB)",
            "monthly_usd": total,
        }]
        assumptions = [
            f"{replicas} pod replicas as specified in deployment scaling config",
            f"Each pod requests {cpu_m}m CPU and {memory_mb}MB memory",
        ]
        return items, assumptions

    def _estimate_database(self, spec_bundle):
        """Estimate database costs from bundle deployment or metadata."""
        deployment = getattr(spec_bundle, "deployment", None)
        dep = {}
        if deployment:
            dep = deployment if isinstance(deployment, dict) else vars(deployment)

        # Try to get DB config from solution metadata
        instance_class = dep.get("database_instance_class", "db.t3.medium")
        storage_gb = dep.get("database_storage_gb", 20)
        multi_az = dep.get("database_multi_az", False)
        backup_days = dep.get("database_backup_days", 7)

        return self._estimate_database_from_config({
            "instance_class": instance_class,
            "storage_gb": storage_gb,
            "multi_az": multi_az,
            "backup_days": backup_days,
        })

    def _estimate_database_from_config(self, cfg):
        instance_class = cfg.get("instance_class", "db.t3.medium")
        storage_gb = cfg.get("storage_gb", 20)
        multi_az = cfg.get("multi_az", False)
        backup_days = cfg.get("backup_days", 7)

        pricing = self.pricing["database"]
        items = []
        assumptions = []

        # Instance cost
        base_cost = pricing.get(instance_class, 49.64)
        instance_cost = base_cost
        label = f"RDS {instance_class}"
        if multi_az:
            instance_cost *= pricing["multi_az_multiplier"]
            label += " (Multi-AZ)"

        items.append({
            "category": "Database",
            "service": label,
            "monthly_usd": round(instance_cost, 2),
        })

        # Storage cost
        storage_cost = round(storage_gb * pricing["storage_per_gb"], 2)
        items.append({
            "category": "Database",
            "service": f"Storage ({storage_gb}GB)",
            "monthly_usd": storage_cost,
        })

        # Backup cost (estimated as storage_gb * backup_days / 30)
        if backup_days > 0:
            backup_gb = storage_gb  # assume full backup size = storage
            backup_cost = round(backup_gb * pricing["backup_per_gb"], 2)
            items.append({
                "category": "Database",
                "service": f"Automated Backups ({backup_days}-day retention)",
                "monthly_usd": backup_cost,
            })
            assumptions.append(
                f"Backup storage estimated at {backup_gb}GB ({backup_days}-day retention)"
            )

        assumptions.append(
            f"RDS {instance_class}{' Multi-AZ' if multi_az else ' Single-AZ'} "
            f"with {storage_gb}GB storage"
        )

        return items, assumptions

    def _estimate_networking(self, services_count):
        pricing = self.pricing["networking"]
        items = []
        assumptions = []

        # ALB
        items.append({
            "category": "Networking",
            "service": "Application Load Balancer",
            "monthly_usd": round(pricing["load_balancer"], 2),
        })

        # Data transfer
        transfer_gb = DEFAULT_DATA_TRANSFER_GB
        transfer_cost = round(transfer_gb * pricing["data_transfer_per_gb"], 2)
        items.append({
            "category": "Networking",
            "service": f"Data Transfer ({transfer_gb}GB)",
            "monthly_usd": transfer_cost,
        })
        assumptions.append(f"Data transfer estimated at {transfer_gb}GB/month")

        # NAT Gateway (if multiple services suggest VPC)
        if services_count > 1:
            items.append({
                "category": "Networking",
                "service": "NAT Gateway",
                "monthly_usd": round(pricing["nat_gateway"], 2),
            })
            assumptions.append("NAT Gateway included for multi-service VPC setup")

        return items, assumptions

    def _estimate_messaging(self, integrations, events):
        items = []
        assumptions = []

        # Check for Kafka/async integrations
        has_kafka = False
        has_sqs = False

        for name, contract in integrations.items():
            protocol = ""
            if isinstance(contract, dict):
                protocol = contract.get("protocol", "")
            elif hasattr(contract, "protocol"):
                protocol = getattr(contract, "protocol", "")

            if protocol in ("kafka", "async", "event"):
                has_kafka = True
            if protocol == "sqs":
                has_sqs = True

        # Events from AsyncAPI spec also indicate async messaging
        if events and not has_kafka:
            has_kafka = True

        if has_kafka:
            kafka_items, kafka_asms = self._estimate_kafka()
            items.extend(kafka_items)
            assumptions.extend(kafka_asms)

        if has_sqs:
            sqs_items, sqs_asms = self._estimate_sqs()
            items.extend(sqs_items)
            assumptions.extend(sqs_asms)

        return items, assumptions

    def _estimate_kafka(self):
        pricing = self.pricing["messaging"]
        brokers = DEFAULT_KAFKA_BROKERS
        cost = round(brokers * pricing["kafka_broker_hour"] * HOURS_PER_MONTH, 2)
        items = [{
            "category": "Messaging",
            "service": f"MSK Kafka ({brokers} brokers)",
            "monthly_usd": cost,
        }]
        assumptions = [f"Amazon MSK with {brokers} brokers (kafka.m5.large equivalent)"]
        return items, assumptions

    def _estimate_sqs(self):
        pricing = self.pricing["messaging"]
        # Assume 10M requests/month
        requests_millions = 10
        cost = round(requests_millions * pricing["sqs_per_million_requests"], 2)
        items = [{
            "category": "Messaging",
            "service": f"SQS ({requests_millions}M requests)",
            "monthly_usd": cost,
        }]
        assumptions = [f"SQS estimated at {requests_millions}M requests/month"]
        return items, assumptions

    def _estimate_monitoring(self, services_count):
        pricing = self.pricing["monitoring"]
        items = []
        assumptions = []

        # CloudWatch metrics
        metrics_count = DEFAULT_METRICS_COUNT * max(services_count, 1)
        metrics_cost = round(metrics_count * pricing["cloudwatch_per_metric"], 2)
        items.append({
            "category": "Monitoring",
            "service": f"CloudWatch Metrics ({metrics_count} custom)",
            "monthly_usd": metrics_cost,
        })

        # CloudWatch logs
        log_gb = DEFAULT_LOG_VOLUME_GB * max(services_count, 1)
        log_cost = round(log_gb * pricing["cloudwatch_logs_per_gb"], 2)
        items.append({
            "category": "Monitoring",
            "service": f"CloudWatch Logs ({log_gb}GB)",
            "monthly_usd": log_cost,
        })

        assumptions.append(
            f"CloudWatch: {metrics_count} custom metrics + {log_gb}GB logs/month"
        )

        return items, assumptions
