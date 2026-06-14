"""
Dashboard Configuration Generator
Creates reusable dashboard configurations using the Hybrid approach
"""
import random
from datetime import datetime, timedelta

from app.services.metrics_service import MetricsService


class DashboardConfig:
    """Base configuration builder for shadcn-styled dashboards"""

    def __init__(self, title, subtitle=""):
        self.title = title
        self.subtitle = subtitle
        self.metrics = []
        self.charts = []
        self.tables = []

    def add_metric(
        self, title, value, trend_value, trend_direction="up", footer_label="", footer_text=""
    ):
        """Add a metric card to dashboard"""
        self.metrics.append(
            {
                "title": title,
                "value": value,
                "trend_value": trend_value,
                "trend_direction": trend_direction,
                "footer_label": footer_label,
                "footer_text": footer_text,
            }
        )
        return self

    def add_chart(self, chart_id, title, subtitle, data, time_ranges=None):
        """Add an area chart to dashboard"""
        self.charts.append(
            {
                "id": chart_id,
                "title": title,
                "subtitle": subtitle,
                "data": data,
                "time_ranges": time_ranges or [],
            }
        )
        return self

    def add_table(
        self,
        table_id,
        tabs,
        columns,
        data,
        show_customize=True,
        show_add_section=True,
        api_endpoint="",
        model_name="Record",
    ):
        """Add a data table to dashboard with optional backend API integration"""
        self.tables.append(
            {
                "id": table_id,
                "table_id": table_id,  # Alias for template compatibility
                "tabs": tabs,
                "columns": columns,
                "data": data,
                "show_customize": show_customize,
                "show_add_section": show_add_section,
                "api_endpoint": api_endpoint,
                "model_name": model_name,
            }
        )
        return self

    def to_dict(self):
        """Convert configuration to dictionary for template rendering"""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "metrics": self.metrics,
            "charts": self.charts,
            "tables": self.tables,
        }


class AdminDashboardConfig:
    """Pre-built configuration for Admin Dashboard"""

    @staticmethod
    def get_config():
        config = DashboardConfig("Admin Dashboard", "Overview of key metrics")

        # Metrics
        config.add_metric(
            "Total Revenue",
            "$1,250.00",
            "+12.5%",
            "up",
            "Trending up this month",
            "Visitors for the last 6 months",
        )
        config.add_metric(
            "New Customers",
            "1,234",
            "-20%",
            "down",
            "Down 20% this period",
            "Acquisition needs attention",
        )
        config.add_metric(
            "Active Accounts",
            "45,678",
            "+12.5%",
            "up",
            "Strong user retention",
            "Engagement exceed targets",
        )
        config.add_metric(
            "Growth Rate",
            "4.5%",
            "+4.5%",
            "up",
            "Steady performance increase",
            "Meets growth projections",
        )

        # Chart data
        chart_data = AdminDashboardConfig._generate_chart_data()
        config.add_chart(
            "adminChart",
            "Total Visitors",
            "Total for the last 3 months",
            chart_data,
            [
                {"label": "Last 3 months", "value": "90d"},
                {"label": "Last 30 days", "value": "30d"},
                {"label": "Last 7 days", "value": "7d"},
            ],
        )

        # Table
        table_data = AdminDashboardConfig._generate_table_data()
        config.add_table(
            "adminTable",
            [
                {"id": "outline", "label": "Outline", "badge": None},
                {"id": "past-performance", "label": "Past Performance", "badge": "3"},
                {"id": "key-personnel", "label": "Key Personnel", "badge": "2"},
                {"id": "focus-documents", "label": "Focus Documents", "badge": None},
            ],
            [
                {"id": "drag", "label": "", "sortable": False},
                {"id": "select", "label": "", "sortable": False},
                {"id": "header", "label": "Header", "sortable": True},
                {"id": "type", "label": "Section Type", "sortable": True},
                {"id": "status", "label": "Status", "sortable": True},
                {"id": "target", "label": "Target", "sortable": True},
                {"id": "limit", "label": "Limit", "sortable": True},
                {"id": "reviewer", "label": "Reviewer", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            table_data,
        )

        return config

    @staticmethod
    def _generate_chart_data():
        """Generate sample chart data"""
        chart_data = []
        start_date = datetime(2024, 4, 1)
        for i in range(90):
            current_date = start_date + timedelta(days=i)
            chart_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "desktop": random.randint(50, 500),
                    "mobile": random.randint(100, 400),
                }
            )
        return chart_data

    @staticmethod
    def _generate_table_data():
        """Generate sample table data"""
        return [
            {
                "id": 1,
                "header": "Cover page",
                "type": "Cover page",
                "status": "In Process",
                "target": "18",
                "limit": "5",
                "reviewer": "Eddie Lake",
            },
            {
                "id": 2,
                "header": "Table of contents",
                "type": "Table of contents",
                "status": "Done",
                "target": "29",
                "limit": "24",
                "reviewer": "Eddie Lake",
            },
            {
                "id": 3,
                "header": "Executive summary",
                "type": "Narrative",
                "status": "Done",
                "target": "10",
                "limit": "13",
                "reviewer": "Eddie Lake",
            },
            {
                "id": 4,
                "header": "Technical approach",
                "type": "Narrative",
                "status": "Done",
                "target": "27",
                "limit": "23",
                "reviewer": "Jamik Tashpulatov",
            },
            {
                "id": 5,
                "header": "Design",
                "type": "Narrative",
                "status": "In Process",
                "target": "2",
                "limit": "16",
                "reviewer": "Jamik Tashpulatov",
            },
            {
                "id": 6,
                "header": "Capabilities",
                "type": "Narrative",
                "status": "In Process",
                "target": "20",
                "limit": "8",
                "reviewer": "Jamik Tashpulatov",
            },
            {
                "id": 7,
                "header": "Integration",
                "type": "Narrative",
                "status": "In Process",
                "target": "19",
                "limit": "21",
                "reviewer": "Jamik Tashpulatov",
            },
            {
                "id": 8,
                "header": "Project timeline",
                "type": "Narrative",
                "status": "Not Started",
                "target": "25",
                "limit": "1",
                "reviewer": "Assign reviewer",
            },
            {
                "id": 9,
                "header": "Cost analysis",
                "type": "Financial",
                "status": "Not Started",
                "target": "12",
                "limit": "29",
                "reviewer": "Assign reviewer",
            },
            {
                "id": 10,
                "header": "Risk assessment",
                "type": "Narrative",
                "status": "Not Started",
                "target": "6",
                "limit": "22",
                "reviewer": "Assign reviewer",
            },
        ]


class SalesDashboardConfig:
    """Pre-built configuration for Sales Dashboard"""

    @staticmethod
    def get_config():
        config = DashboardConfig("Sales Dashboard", "Track your sales performance")

        # Sales metrics
        config.add_metric(
            "Total Sales",
            "$45,231.89",
            "+20.1%",
            "up",
            "Strong sales growth",
            "Best month this quarter",
        )
        config.add_metric(
            "Orders", "2,350", "+180", "up", "180 new orders", "Compared to last month"
        )
        config.add_metric(
            "Conversion Rate",
            "3.2%",
            "+0.5%",
            "up",
            "Improved conversion",
            "Marketing efforts paying off",
        )
        config.add_metric(
            "Average Order",
            "$19.25",
            "-2.1%",
            "down",
            "Slightly lower AOV",
            "Within acceptable range",
        )

        # Sales chart
        chart_data = SalesDashboardConfig._generate_sales_chart_data()
        config.add_chart(
            "salesChart",
            "Revenue Over Time",
            "Daily revenue for the last 90 days",
            chart_data,
            [
                {"label": "Last 90 days", "value": "90d"},
                {"label": "Last 30 days", "value": "30d"},
                {"label": "Last 7 days", "value": "7d"},
            ],
        )

        # Top products table
        table_data = SalesDashboardConfig._generate_products_table()
        config.add_table(
            "salesTable",
            [
                {"id": "products", "label": "Top Products", "badge": None},
                {"id": "customers", "label": "Top Customers", "badge": "5"},
                {"id": "regions", "label": "By Region", "badge": None},
            ],
            [
                {"id": "select", "label": "", "sortable": False},
                {"id": "product", "label": "Product", "sortable": True},
                {"id": "revenue", "label": "Revenue", "sortable": True},
                {"id": "units", "label": "Units Sold", "sortable": True},
                {"id": "growth", "label": "Growth", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            table_data,
            show_add_section=False,
        )

        return config

    @staticmethod
    def _generate_sales_chart_data():
        """Generate sales chart data"""
        chart_data = []
        start_date = datetime(2024, 4, 1)
        for i in range(90):
            current_date = start_date + timedelta(days=i)
            chart_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "desktop": random.randint(1000, 5000),
                    "mobile": random.randint(500, 3000),
                }
            )
        return chart_data

    @staticmethod
    def _generate_products_table():
        """Generate products table data"""
        return [
            {
                "id": 1,
                "product": "Product A",
                "revenue": "$12,345",
                "units": "456",
                "growth": "+15%",
            },
            {
                "id": 2,
                "product": "Product B",
                "revenue": "$9,876",
                "units": "321",
                "growth": "+22%",
            },
            {"id": 3, "product": "Product C", "revenue": "$7,654", "units": "234", "growth": "+8%"},
            {"id": 4, "product": "Product D", "revenue": "$5,432", "units": "189", "growth": "-5%"},
            {
                "id": 5,
                "product": "Product E",
                "revenue": "$3,210",
                "units": "145",
                "growth": "+12%",
            },
        ]


# ============================================================================
# ENTERPRISE METRICS DASHBOARDS
# ============================================================================


class ExecutiveDashboardConfig:
    """Executive Dashboard - Portfolio Health & Strategic View"""

    @staticmethod
    def get_config():
        config = DashboardConfig(
            "Executive Dashboard",
            "Portfolio health, strategic initiatives, and business value metrics",
        )

        # Get real metrics from database with error handling
        try:
            tech_debt = MetricsService.get_technical_debt_index()
        except Exception as e:
            print(f"Error getting tech debt: {e}")
            tech_debt = {
                "overall_index": 0,
                "total_apps": 0,
                "high_debt_apps": 0,
                "avg_debt_hours": 0,
                "total_debt_hours": 0,
            }

        try:
            capability_coverage = MetricsService.get_capability_coverage()
        except Exception as e:
            print(f"Error getting capability coverage: {e}")
            capability_coverage = {
                "capabilities": [],
                "summary": {"total": 0, "gaps": 0, "at_risk": 0, "covered": 0},
            }

        try:
            cloud_readiness = MetricsService.get_cloud_migration_readiness()
        except Exception as e:
            print(f"Error getting cloud readiness: {e}")
            cloud_readiness = {
                "applications": [],
                "summary": {
                    "total": 0,
                    "high_readiness": 0,
                    "medium_readiness": 0,
                    "low_readiness": 0,
                    "avg_readiness": 0,
                },
            }

        try:
            security = MetricsService.get_security_posture()
        except Exception as e:
            print(f"Error getting security posture: {e}")
            security = {
                "overall_score": 0,
                "total_interfaces": 0,
                "with_auth": 0,
                "with_encryption": 0,
            }

        # Calculate Portfolio Health Index from component scores (avoid duplicate queries)
        tech_debt_score = max(0, 100 - tech_debt["overall_index"])
        cloud_score = cloud_readiness["summary"]["avg_readiness"]
        coverage_score = (
            (
                capability_coverage["summary"]["covered"]
                / capability_coverage["summary"]["total"]
                * 100
            )
            if capability_coverage["summary"]["total"] > 0
            else 0
        )
        security_score = security["overall_score"]

        health_score = round(
            (
                tech_debt_score * 0.25
                + cloud_score * 0.25
                + coverage_score * 0.25
                + security_score * 0.25
            ),
            1,
        )
        health_trend = "+" + str(round(health_score - 65, 1)) + "%"  # Mock trend
        config.add_metric(
            "Portfolio Health",
            f"{health_score}%",
            health_trend,
            "up" if health_score > 70 else "down",
            f"Composite score across 4 dimensions",
            f'{tech_debt["total_apps"]} applications assessed',
        )

        # Technical Debt Index
        debt_index = tech_debt["overall_index"]
        config.add_metric(
            "Technical Debt Index",
            f"{debt_index}",
            f'{tech_debt["high_debt_apps"]} apps',
            "down" if debt_index < 50 else "up",
            f"High debt applications",
            f'Average: {tech_debt["avg_debt_hours"]}h per app',
        )

        # Capability Coverage
        coverage = capability_coverage["summary"]
        coverage_pct = round(
            (coverage["covered"] / coverage["total"] * 100) if coverage["total"] > 0 else 0, 1
        )
        config.add_metric(
            "Capability Coverage",
            f"{coverage_pct}%",
            f"{coverage['gaps']} gaps",
            "up" if coverage["gaps"] < 10 else "down",
            f'{coverage["gaps"]} capabilities without apps',
            f'{coverage["covered"]} of {coverage["total"]} covered',
        )

        # Cloud Migration Progress
        cloud_summary = cloud_readiness["summary"]
        config.add_metric(
            "Cloud Readiness",
            f"{cloud_summary['avg_readiness']}%",
            f"+{cloud_summary['high_readiness']} ready",
            "up",
            f'{cloud_summary["high_readiness"]} apps ready for cloud',
            f'{cloud_summary["low_readiness"]} apps need modernization',
        )

        # Capability Coverage Table - All capabilities data
        cap_table_data = []
        gap_count = 0
        for cap in capability_coverage["capabilities"]:  # All capabilities
            cap_table_data.append(
                {
                    "id": cap["id"],
                    "header": cap["name"],
                    "type": cap["domain"],
                    "status": "L" + str(cap["level"]),
                    "target": str(cap["app_count"]),
                    "limit": "M" + str(cap["maturity"]),
                    "reviewer": cap["status"],
                }
            )
            if cap["status"] in ["GAP - No Applications", "AT RISK - Single App"]:
                gap_count += 1

        # Single table with 'outline' as first tab ID so JS recognizes it
        config.add_table(
            "capabilityTable",
            [
                {
                    "id": "outline",
                    "label": "Business Capabilities",
                    "badge": str(len(cap_table_data)),
                },
                {"id": "gap-analysis", "label": "Gap Analysis", "badge": str(gap_count)},
                {
                    "id": "modernization",
                    "label": "Modernization Pipeline",
                    "badge": str(
                        cloud_summary["low_readiness"] + cloud_summary["medium_readiness"]
                    ),
                },
            ],
            [
                {"id": "select", "label": "", "sortable": False},
                {"id": "header", "label": "Capability", "sortable": True},
                {"id": "type", "label": "Domain", "sortable": True},
                {"id": "status", "label": "Level", "sortable": True},
                {"id": "target", "label": "Apps", "sortable": True},
                {"id": "limit", "label": "Maturity", "sortable": True},
                {"id": "reviewer", "label": "Status", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            cap_table_data,
            show_add_section=False,
        )

        return config


class ArchitectureDashboardConfig:
    """Architecture Review Board Dashboard"""

    @staticmethod
    def get_config():
        config = DashboardConfig(
            "Architecture Review Board Dashboard",
            "Technical debt, integration complexity, and architecture compliance metrics",
        )

        # Get real metrics with error handling
        try:
            tech_debt = MetricsService.get_technical_debt_index()
        except Exception as e:
            print(f"Error getting tech debt: {e}")
            tech_debt = {
                "overall_index": 0,
                "total_apps": 0,
                "high_debt_apps": 0,
                "avg_debt_hours": 0,
                "total_debt_hours": 0,
            }

        try:
            integration = MetricsService.get_integration_complexity()
        except Exception as e:
            print(f"Error getting integration complexity: {e}")
            integration = {
                "applications": [],
                "summary": {"very_high": 0, "high": 0, "medium": 0, "low": 0},
            }

        try:
            security = MetricsService.get_security_posture()
        except Exception as e:
            print(f"Error getting security posture: {e}")
            security = {
                "overall_score": 0,
                "total_interfaces": 0,
                "with_auth": 0,
                "with_encryption": 0,
            }

        # Technical Debt Metric
        config.add_metric(
            "Avg Technical Debt",
            f"{tech_debt.get('avg_debt_hours', 0)}h",
            f"{tech_debt.get('high_debt_apps', 0)} apps",
            "down" if tech_debt.get("avg_debt_hours", 0) < 100 else "up",
            f"High debt applications need refactoring",
            f'Total: {tech_debt.get("total_debt_hours", 0)} hours across portfolio',
        )

        # Integration Complexity
        int_summary = integration["summary"]
        high_complexity = int_summary["very_high"] + int_summary["high"]
        config.add_metric(
            "High Complexity Apps",
            str(high_complexity),
            f"{int_summary['very_high']} critical",
            "down",
            f"Very high integration complexity",
            f'{len(integration["applications"])} apps analyzed',
        )

        # Security Posture
        config.add_metric(
            "Security Posture",
            f"{security['overall_score']}%",
            f"{security['with_auth']} secure",
            "up" if security["overall_score"] > 70 else "down",
            f'{security["with_auth"]} of {security["total_interfaces"]} with auth',
            f'{security["with_encryption"]} with encryption',
        )

        # Architecture Standards
        config.add_metric(
            "Standards Compliance",
            "87.5%",  # Mock metric
            "+5.2%",
            "up",
            "Architecture patterns compliance",
            "Monthly assessment",
        )

        # Integration Complexity Table
        int_table_data = []
        for app in integration["applications"][:20]:
            int_table_data.append(
                {
                    "id": app["id"],
                    "header": app["name"],
                    "type": app["complexity"],
                    "status": str(app["interface_count"]) + " APIs",
                    "target": str(app["consumer_count"]),
                    "limit": str(int(app["avg_latency"])) + "ms",
                    "reviewer": "Review" if app["complexity"] in ["VERY HIGH", "HIGH"] else "OK",
                }
            )

        config.add_table(
            "architectureTable",
            [
                {"id": "outline", "label": "Integration Complexity", "badge": str(high_complexity)},
                {
                    "id": "tech-debt",
                    "label": "Technical Debt",
                    "badge": str(tech_debt["high_debt_apps"]),
                },
                {"id": "patterns", "label": "Architecture Patterns", "badge": None},
            ],
            [
                {"id": "select", "label": "", "sortable": False},
                {"id": "header", "label": "Application", "sortable": True},
                {"id": "type", "label": "Complexity", "sortable": True},
                {"id": "status", "label": "Interfaces", "sortable": True},
                {"id": "target", "label": "Consumers", "sortable": True},
                {"id": "limit", "label": "Latency", "sortable": True},
                {"id": "reviewer", "label": "Action", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            int_table_data,
            show_add_section=False,
        )

        return config


class OperationsDashboardConfig:
    """Operations Dashboard - SLA, Service Quality, Incidents"""

    @staticmethod
    def get_config():
        config = DashboardConfig(
            "Operations Dashboard", "Service quality, SLA compliance, and operational metrics"
        )

        # Get real metrics with error handling
        try:
            service_quality = MetricsService.get_service_quality_index()
        except Exception as e:
            print(f"Error getting service quality: {e}")
            service_quality = {
                "service_count": 0,
                "avg_sla_target": 99.0,
                "avg_actual": 0,
                "sla_compliance": 0,
                "customer_satisfaction": 0,
            }

        # SLA Compliance
        config.add_metric(
            "SLA Compliance",
            f"{service_quality['sla_compliance']}%",
            "+2.1%",
            "up" if service_quality["sla_compliance"] > 95 else "down",
            "Overall service level achievement",
            f'{service_quality["service_count"]} services tracked',
        )

        # Availability
        config.add_metric(
            "Avg Availability",
            f"{service_quality['avg_actual']}%",
            f"Target: {service_quality['avg_sla_target']}%",
            "up" if service_quality["avg_actual"] >= service_quality["avg_sla_target"] else "down",
            "Actual vs SLA target",
            "Last 30 days",
        )

        # Customer Satisfaction
        config.add_metric(
            "Customer Satisfaction",
            f"{service_quality['customer_satisfaction']}/5",
            "+0.3",
            "up",
            "Average satisfaction score",
            "Based on user surveys",
        )

        # Incidents — no incident tracking table exists
        config.add_metric(
            "Open Incidents",
            "\u2014",
            "N/A",
            "neutral",
            "Not configured",
            "Incident tracking not available",
        )

        # Services Table
        service_table_data = [
            {
                "id": 1,
                "header": "Customer Portal",
                "type": "Web Service",
                "status": "99.8%",
                "target": "99.5%",
                "limit": "150ms",
                "reviewer": "✓ Compliant",
            },
            {
                "id": 2,
                "header": "Order API",
                "type": "REST API",
                "status": "99.9%",
                "target": "99.9%",
                "limit": "85ms",
                "reviewer": "✓ Compliant",
            },
            {
                "id": 3,
                "header": "Payment Gateway",
                "type": "Integration",
                "status": "98.2%",
                "target": "99.0%",
                "limit": "320ms",
                "reviewer": "⚠ At Risk",
            },
            {
                "id": 4,
                "header": "Inventory Service",
                "type": "Microservice",
                "status": "99.5%",
                "target": "99.0%",
                "limit": "95ms",
                "reviewer": "✓ Compliant",
            },
            {
                "id": 5,
                "header": "Auth Service",
                "type": "Core Service",
                "status": "99.95%",
                "target": "99.9%",
                "limit": "45ms",
                "reviewer": "✓ Compliant",
            },
        ]

        config.add_table(
            "operationsTable",
            [
                {"id": "outline", "label": "Service Quality", "badge": None},
                {"id": "incidents", "label": "Active Incidents", "badge": "23"},
                {"id": "changes", "label": "Change Schedule", "badge": "8"},
            ],
            [
                {"id": "select", "label": "", "sortable": False},
                {"id": "header", "label": "Service", "sortable": True},
                {"id": "type", "label": "Type", "sortable": True},
                {"id": "status", "label": "Availability", "sortable": True},
                {"id": "target", "label": "SLA Target", "sortable": True},
                {"id": "limit", "label": "Response Time", "sortable": True},
                {"id": "reviewer", "label": "Status", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            service_table_data,
            show_add_section=False,
        )

        return config


class FinancialDashboardConfig:
    """Financial Dashboard - Costs, TCO, ROI, Budget"""

    @staticmethod
    def get_config():
        config = DashboardConfig(
            "Financial Dashboard",
            "IT spend, cost optimization, vendor management, and budget tracking",
        )

        # Get real metrics with error handling
        try:
            portfolio_cost = MetricsService.get_total_portfolio_cost()
        except Exception as e:
            print(f"Error getting portfolio cost: {e}")
            portfolio_cost = {"total_tco": 0, "breakdown": {}, "app_count": 0}

        try:
            optimization = MetricsService.get_cost_optimization_opportunities()
        except Exception as e:
            print(f"Error getting optimization opportunities: {e}")
            optimization = {"total_savings": 0, "opportunity_count": 0, "top_opportunities": []}

        try:
            vendor_risk = MetricsService.get_vendor_concentration_risk()
        except Exception as e:
            print(f"Error getting vendor risk: {e}")
            vendor_risk = {
                "vendors": [],
                "total_spend": 0,
                "critical_risk_count": 0,
                "high_risk_count": 0,
            }

        # Total IT Spend
        total_spend = portfolio_cost["total_tco"]
        config.add_metric(
            "Total IT Spend",
            f"${total_spend:,.0f}",
            "+8.5%",  # Mock YoY
            "up",
            "Annual IT expenditure",
            f'{portfolio_cost["app_count"]} applications',
        )

        # Cost Optimization Potential
        config.add_metric(
            "Optimization Potential",
            f"${optimization['total_savings']:,.0f}",
            f"{optimization['opportunity_count']} opportunities",
            "up",
            f"Potential savings from consolidation",
            f'{optimization["opportunity_count"]} app pairs identified',
        )

        # Vendor Concentration Risk
        config.add_metric(
            "Vendor Concentration",
            str(vendor_risk["critical_risk_count"]),
            f"{vendor_risk['high_risk_count']} high risk",
            "down" if vendor_risk["critical_risk_count"] == 0 else "up",
            f"Critical vendor dependencies",
            f'Total vendor spend: ${vendor_risk["total_spend"]:,.0f}',
        )

        # Budget Variance — no budget tracking table exists
        config.add_metric(
            "Budget Variance",
            "\u2014",
            "N/A",
            "neutral",
            "Not configured",
            "Budget tracking not available",
        )

        # Cost Breakdown Table
        cost_table_data = [
            {
                "id": 1,
                "header": "Software Licensing",
                "type": "Operating",
                "status": f"${portfolio_cost['breakdown'].get('licensing', 0):,.0f}",
                "target": "35%",
                "limit": "+2.1%",
                "reviewer": "On Track",
            },
            {
                "id": 2,
                "header": "Cloud Services",
                "type": "Operating",
                "status": f"${portfolio_cost['breakdown'].get('cloud', 0):,.0f}",
                "target": "28%",
                "limit": "+15.3%",
                "reviewer": "Growing",
            },
            {
                "id": 3,
                "header": "Infrastructure",
                "type": "Operating",
                "status": f"${portfolio_cost['breakdown'].get('infrastructure', 0):,.0f}",
                "target": "22%",
                "limit": "-5.2%",
                "reviewer": "Declining",
            },
            {
                "id": 4,
                "header": "Support & Maintenance",
                "type": "Operating",
                "status": f"${portfolio_cost['breakdown'].get('support', 0) + portfolio_cost['breakdown'].get('maintenance', 0):,.0f}",
                "target": "15%",
                "limit": "+1.8%",
                "reviewer": "Stable",
            },
        ]

        config.add_table(
            "financialTable",
            [
                {"id": "outline", "label": "Cost Breakdown", "badge": None},
                {
                    "id": "optimization",
                    "label": "Savings Opportunities",
                    "badge": str(optimization["opportunity_count"]),
                },
                {
                    "id": "vendors",
                    "label": "Top Vendors",
                    "badge": str(vendor_risk["critical_risk_count"]),
                },
            ],
            [
                {"id": "select", "label": "", "sortable": False},
                {"id": "header", "label": "Category", "sortable": True},
                {"id": "type", "label": "Type", "sortable": True},
                {"id": "status", "label": "Annual Cost", "sortable": True},
                {"id": "target", "label": "% of Total", "sortable": True},
                {"id": "limit", "label": "YoY Change", "sortable": True},
                {"id": "reviewer", "label": "Trend", "sortable": True},
                {"id": "actions", "label": "", "sortable": False},
            ],
            cost_table_data,
            show_add_section=False,
        )

        return config
