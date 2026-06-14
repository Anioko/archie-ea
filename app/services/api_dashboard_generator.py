"""
API Dashboard Generator Service

Automatically generates shadcn-styled dashboards from REST APIs.
Supports OpenAPI/Swagger specs and live API introspection.
"""
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # dead-code-ok
from urllib.parse import urljoin, urlparse

import requests

from app.utils.dashboard_config import DashboardConfig

from .llm_service import LLMService
from .metric_calculation_service import MetricCalculationService

logger = logging.getLogger(__name__)


class APIDashboardGenerator:
    """Generate dashboards from API specifications"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self.metric_calculator = MetricCalculationService()

    def get_charts(self, dashboard_type: str) -> Dict:
        """Get chart data for a dashboard type."""
        return {
            "dashboard_type": dashboard_type,
            "charts": [],
            "message": "Chart generation requires dashboard configuration",
        }

    def get_tables(self, dashboard_type: str) -> Dict:
        """Get table data for a dashboard type."""
        return {
            "dashboard_type": dashboard_type,
            "tables": [],
            "message": "Table generation requires dashboard configuration",
        }

    def get_metrics(self, dashboard_type: str) -> Dict:
        """Get metrics for a dashboard type."""
        return {
            "dashboard_type": dashboard_type,
            "metrics": [],
            "message": "Metric generation requires dashboard configuration",
        }

    def get_realtime_data(self, dashboard_type: str) -> Dict:
        """Get realtime data for a dashboard type."""
        return {
            "dashboard_type": dashboard_type,
            "realtime_data": [],
            "message": "Realtime data requires configured data sources",
        }

    def generate_from_schema(self, schema: Dict) -> Dict:
        """
        Generate dashboard from JSON schema - SHADCN PATTERN

        This is the core method that mimics shadcn's dashboard-generator:
        1. Takes a schema definition (fields, count, config)
        2. Generates mock data based on schema types
        3. Returns dashboard configuration with generated data

        Args:
            schema: {
                "fields": [{"name": "...", "type": "string|number|date|status|...", "values": [...], "range": {...}}],
                "count": 10,
                "dashboard": {"title": "...", "layout": "grid", "sections": [...]}
            }

        Returns:
            Dashboard configuration with generated mock data
        """
        logger.info(
            f"Generating dashboard from schema: {schema.get('dashboard', {}).get('title', 'Untitled')}"
        )

        fields = schema.get("fields", [])
        dashboard_config = schema.get("dashboard", {})
        title = dashboard_config.get("title", "Generated Dashboard")
        sections = dashboard_config.get("sections", [])

        config = DashboardConfig(
            title=title,
            subtitle=dashboard_config.get(
                "description", "Schema-generated dashboard — no data source configured"
            ),
        )

        # Add a status metric indicating no real data source
        config.add_metric(
            title="Status",
            value="No data source configured",
            trend_value="\u2014",
            trend_direction="neutral",
            footer_label="Configure a real data source",
            footer_text="Schema-generated dashboards require a database or API data source",
        )

        # Build table structure from schema fields (empty, but with columns)
        if fields:
            columns = []
            for field in fields:
                columns.append(
                    {
                        "id": field["name"],
                        "label": field.get("label", field["name"].replace("_", " ").title()),
                        "type": self._map_field_type_to_column_type(field["type"]),
                        "visible": True,
                    }
                )

            config.add_table(
                table_id="generated_table",
                tabs=[{"id": "all", "label": "All Data", "count": 0}],
                columns=columns,
                data=[],
                show_customize=True,
                show_add_section=True,
            )

        logger.info(
            f"Generated empty dashboard layout: {len(config.metrics)} metrics, {len(config.tables)} tables (no data source)"
        )

        return config.to_dict()

    def _map_field_type_to_column_type(self, field_type: str) -> str:
        """Map schema field types to table column types"""
        mapping = {
            "string": "text",
            "number": "number",
            "currency": "text",
            "percentage": "text",
            "date": "text",
            "status": "badge",
            "email": "text",
            "url": "text",
            "boolean": "badge",
        }
        return mapping.get(field_type, "text")

    def generate_from_openapi(
        self,
        openapi_url: str,
        api_name: str,
        api_base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> DashboardConfig:
        """
        Generate dashboard config from OpenAPI/Swagger specification.

        Args:
            openapi_url: URL to OpenAPI spec (JSON/YAML)
            api_name: Display name for the dashboard
            api_base_url: Base URL for API calls (if different from spec)
            auth_token: Optional Bearer token for API authentication

        Returns:
            DashboardConfig ready to render
        """
        try:
            # Fetch OpenAPI spec
            logger.info(f"Fetching OpenAPI spec from {openapi_url}")
            response = requests.get(openapi_url, timeout=10)
            response.raise_for_status()

            # Handle YAML or JSON
            content_type = response.headers.get("content-type", "")
            if (
                "yaml" in content_type
                or openapi_url.endswith(".yaml")
                or openapi_url.endswith(".yml")
            ):
                import yaml

                spec = yaml.safe_load(response.text)
            else:
                spec = response.json()

            # Extract base URL from spec if not provided
            if not api_base_url:
                api_base_url = self._extract_base_url(spec, openapi_url)

            logger.info(f"Generating dashboard for {api_name} from OpenAPI spec")

            # Create dashboard config
            config = DashboardConfig(
                title=f"{api_name} Dashboard",
                subtitle=spec.get("info", {}).get(
                    "description", f"Auto-generated from {api_name} API"
                ),
            )

            # Parse endpoints and generate dashboard components
            paths = spec.get("paths", {})

            # Step 1: Identify list/collection endpoints for tables
            list_endpoints = self._identify_list_endpoints(paths, spec)

            # Step 2: Identify metric endpoints for cards
            metric_endpoints = self._identify_metric_endpoints(paths, spec)

            # Step 3: Identify time-series endpoints for charts
            timeseries_endpoints = self._identify_timeseries_endpoints(paths, spec)

            # Generate metric cards
            for endpoint_info in metric_endpoints[:4]:  # Limit to 4 cards
                metric = self._generate_metric_card(endpoint_info, api_base_url, auth_token)
                if metric:
                    config.add_metric(**metric)

            # Generate charts
            for endpoint_info in timeseries_endpoints[:1]:  # Limit to 1 chart
                chart = self._generate_chart(endpoint_info, api_base_url, auth_token)
                if chart:
                    config.add_chart(**chart)

            # Generate tables
            for endpoint_info in list_endpoints[:3]:  # Limit to 3 tables
                table = self._generate_table(endpoint_info, api_base_url, auth_token, spec)
                if table:
                    config.add_table(**table)

            # Store metadata for runtime
            config.metadata = {
                "api_base_url": api_base_url,
                "auth_token": auth_token,
                "openapi_url": openapi_url,
                "generated_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Dashboard generated: {len(config.metrics)} metrics, "
                f"{len(config.charts)} charts, {len(config.tables)} tables"
            )

            return config

        except Exception as e:
            logger.error(f"Failed to generate dashboard from OpenAPI: {str(e)}")
            raise

    def generate_from_live_api(
        self,
        api_endpoint: str,
        api_name: str,
        auth_token: Optional[str] = None,
        sample_size: int = 10,
    ) -> DashboardConfig:
        """
        Generate dashboard by introspecting a live API endpoint.

        Args:
            api_endpoint: Direct API endpoint URL
            api_name: Display name for dashboard
            auth_token: Optional Bearer token
            sample_size: Number of records to fetch for schema inference

        Returns:
            DashboardConfig
        """
        try:
            logger.info(f"Introspecting live API: {api_endpoint}")

            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            # Fetch sample data
            response = requests.get(api_endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Create config
            config = DashboardConfig(
                title=f"{api_name} Dashboard", subtitle=f"Auto-generated from {api_endpoint}"
            )

            # Analyze response structure
            if isinstance(data, list):
                # List response → Table
                if len(data) > 0:
                    columns = self._infer_columns_from_data(data[0])
                    config.add_table(
                        table_id="main_table",
                        tabs=[{"id": "all", "label": "All Records", "count": len(data)}],
                        columns=columns,
                        data=data[:50],  # Limit to 50 rows
                        show_customize=True,
                        show_add_section=True,
                    )

            elif isinstance(data, dict):
                # Object response → Extract metrics and nested lists

                # Extract scalar values as metrics
                metrics = self._extract_metrics_from_object(data)
                for metric in metrics[:4]:
                    config.add_metric(**metric)

                # Extract arrays as tables
                tables = self._extract_tables_from_object(data)
                for table in tables[:2]:
                    config.add_table(**table)

            config.metadata = {
                "api_endpoint": api_endpoint,
                "auth_token": auth_token,
                "generated_at": datetime.utcnow().isoformat(),
            }

            return config

        except Exception as e:
            logger.error(f"Failed to introspect API: {str(e)}")
            raise

    def generate_with_llm(
        self,
        api_endpoint: str,
        api_name: str,
        requirements: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> DashboardConfig:
        """
        Use LLM to intelligently generate dashboard from API.

        Args:
            api_endpoint: API endpoint URL or OpenAPI spec URL
            api_name: Display name
            requirements: Optional user requirements for dashboard
            auth_token: Optional auth token

        Returns:
            DashboardConfig
        """
        try:
            logger.info(f"Using LLM to generate dashboard for {api_name}")

            # Fetch API sample
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = requests.get(api_endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            api_sample = response.text[:2000]  # Limit to 2000 chars

            # Build LLM prompt
            prompt = self._build_llm_prompt(api_name, api_sample, requirements)

            # Call LLM
            llm_response = self.llm_service.generate_text(
                prompt=prompt, model="gpt - 4", temperature=0.3
            )

            # Parse LLM response into config
            config = self._parse_llm_response(llm_response, api_name, api_endpoint)

            config.metadata = {
                "api_endpoint": api_endpoint,
                "auth_token": auth_token,
                "generated_at": datetime.utcnow().isoformat(),
                "generation_method": "llm",
            }

            return config

        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            # Fallback to live API introspection
            logger.info("Falling back to live API introspection")
            return self.generate_from_live_api(api_endpoint, api_name, auth_token)

    # Helper methods

    def _extract_base_url(self, spec: Dict, openapi_url: str) -> str:
        """Extract base API URL from OpenAPI spec"""
        # Try servers array (OpenAPI 3.x)
        servers = spec.get("servers", [])
        if servers:
            return servers[0].get("url", "")

        # Try host + basePath (Swagger 2.0)
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        if host:
            scheme = spec.get("schemes", ["https"])[0]
            return f"{scheme}://{host}{base_path}"

        # Fallback to openapi_url domain
        parsed = urlparse(openapi_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _identify_list_endpoints(self, paths: Dict, spec: Dict) -> List[Dict]:
        """Identify endpoints that return lists/collections"""
        list_endpoints = []

        for path, methods in paths.items():
            if "get" in methods:
                method_spec = methods["get"]

                # Check if response is array
                responses = method_spec.get("responses", {})
                success_response = responses.get("200", {})
                content = success_response.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})

                # Check for array type
                if schema.get("type") == "array" or "items" in schema:
                    list_endpoints.append(
                        {"path": path, "method": "get", "spec": method_spec, "schema": schema}
                    )

        return list_endpoints

    def _identify_metric_endpoints(self, paths: Dict, spec: Dict) -> List[Dict]:
        """Identify endpoints that return scalar metrics"""
        metric_endpoints = []

        for path, methods in paths.items():
            # Look for stats, metrics, count, total in path
            if any(
                keyword in path.lower()
                for keyword in ["stats", "metrics", "count", "total", "summary"]
            ):
                if "get" in methods:
                    metric_endpoints.append({"path": path, "method": "get", "spec": methods["get"]})

        return metric_endpoints

    def _identify_timeseries_endpoints(self, paths: Dict, spec: Dict) -> List[Dict]:
        """Identify endpoints that return time-series data"""
        timeseries_endpoints = []

        for path, methods in paths.items():
            # Look for time-related keywords
            if any(
                keyword in path.lower()
                for keyword in ["history", "trend", "timeseries", "analytics"]
            ):
                if "get" in methods:
                    timeseries_endpoints.append(
                        {"path": path, "method": "get", "spec": methods["get"]}
                    )

        return timeseries_endpoints

    def _generate_metric_card(
        self, endpoint_info: Dict, base_url: str, auth_token: Optional[str]
    ) -> Optional[Dict]:
        """Generate metric card from endpoint"""
        try:
            url = urljoin(base_url, endpoint_info["path"])
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()

            # Extract metric
            if isinstance(data, dict):
                # Look for common metric patterns
                value = (
                    data.get("total")
                    or data.get("count")
                    or data.get("value")
                    or list(data.values())[0]
                )
                title = endpoint_info["spec"].get(
                    "summary", endpoint_info["path"].split("/")[-1].title()
                )

                return {
                    "title": title,
                    "value": str(value),
                    "trend_value": "+5%",
                    "trend_direction": "up",
                    "footer_label": "Current period",
                    "footer_text": datetime.now().strftime("%B %Y"),
                }
        except Exception as e:
            logger.warning(f"Failed to generate metric from {endpoint_info['path']}: {str(e)}")
            return None

    def _generate_chart(
        self, endpoint_info: Dict, base_url: str, auth_token: Optional[str]
    ) -> Optional[Dict]:
        """Generate chart from time-series endpoint"""
        try:
            url = urljoin(base_url, endpoint_info["path"])
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()

            # Convert to chart format
            if isinstance(data, list):
                chart_data = [
                    {
                        "date": item.get("date") or item.get("timestamp") or f"Day {i + 1}",
                        "value": item.get("value") or item.get("count") or 0,
                    }
                    for i, item in enumerate(data[:90])  # Limit to 90 points
                ]

                return {
                    "chart_id": f"chart_{endpoint_info['path'].replace('/', '_')}",
                    "title": endpoint_info["spec"].get("summary", "Time Series"),
                    "subtitle": f"Data from {endpoint_info['path']}",
                    "data": chart_data,
                    "time_ranges": [
                        {"id": "90d", "label": "Last 3 months"},
                        {"id": "30d", "label": "Last 30 days"},
                        {"id": "7d", "label": "Last 7 days"},
                    ],
                }
        except Exception as e:
            logger.warning(f"Failed to generate chart from {endpoint_info['path']}: {str(e)}")
            return None

    def _generate_table(
        self, endpoint_info: Dict, base_url: str, auth_token: Optional[str], spec: Dict
    ) -> Optional[Dict]:
        """Generate data table from list endpoint"""
        try:
            url = urljoin(base_url, endpoint_info["path"])
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = requests.get(url, headers=headers, timeout=5)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                columns = self._infer_columns_from_schema(endpoint_info["schema"], data[0])

                return {
                    "table_id": f"table_{endpoint_info['path'].replace('/', '_')}",
                    "tabs": [{"id": "all", "label": "All", "count": len(data)}],
                    "columns": columns,
                    "data": data[:100],  # Limit to 100 rows
                    "show_customize": True,
                    "show_add_section": True,
                }
        except Exception as e:
            logger.warning(f"Failed to generate table from {endpoint_info['path']}: {str(e)}")
            return None

    def _infer_columns_from_schema(self, schema: Dict, sample_row: Dict) -> List[Dict]:
        """Infer table columns from OpenAPI schema and sample data"""
        columns = []

        # Get properties from schema
        items = schema.get("items", {})
        properties = items.get("properties", {})

        if properties:
            for prop_name, prop_spec in properties.items():
                columns.append(
                    {
                        "id": prop_name,
                        "label": prop_name.replace("_", " ").title(),
                        "type": self._map_openapi_type_to_column_type(
                            prop_spec.get("type", "string")
                        ),
                        "visible": True,
                    }
                )
        else:
            # Fallback to sample data
            columns = self._infer_columns_from_data(sample_row)

        return columns

    def _infer_columns_from_data(self, sample_row: Dict) -> List[Dict]:
        """Infer columns from sample data"""
        columns = []

        for key, value in sample_row.items():
            col_type = "text"
            if isinstance(value, (int, float)):
                col_type = "number"
            elif isinstance(value, bool):
                col_type = "badge"
            elif key.lower() in ["status", "state", "type"]:
                col_type = "badge"

            columns.append(
                {
                    "id": key,
                    "label": key.replace("_", " ").title(),
                    "type": col_type,
                    "visible": True,
                }
            )

        return columns

    def _map_openapi_type_to_column_type(self, openapi_type: str) -> str:
        """Map OpenAPI data types to column types"""
        mapping = {
            "string": "text",
            "integer": "number",
            "number": "number",
            "boolean": "badge",
            "array": "text",
            "object": "text",
        }
        return mapping.get(openapi_type, "text")

    def _extract_metrics_from_object(self, data: Dict) -> List[Dict]:
        """Extract scalar metrics from object"""
        metrics = []

        for key, value in data.items():
            if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                metrics.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "trend_value": "+0%",
                        "trend_direction": "up",
                        "footer_label": "Current value",
                        "footer_text": datetime.now().strftime("%B %Y"),
                    }
                )

        return metrics

    def _extract_tables_from_object(self, data: Dict) -> List[Dict]:
        """Extract nested arrays as tables"""
        tables = []

        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                columns = self._infer_columns_from_data(value[0])
                tables.append(
                    {
                        "table_id": f"table_{key}",
                        "tabs": [{"id": "all", "label": key.title(), "count": len(value)}],
                        "columns": columns,
                        "data": value[:50],
                        "show_customize": True,
                        "show_add_section": True,
                    }
                )

        return tables

    def _build_llm_prompt(self, api_name: str, api_sample: str, requirements: Optional[str]) -> str:
        """Build prompt for LLM dashboard generation"""
        prompt = f"""
Analyze this API response and generate a dashboard configuration.

API: {api_name}

Sample Response:
{api_sample}

Requirements: {requirements or 'Create a comprehensive dashboard'}

Generate a JSON configuration with:
1. Metric cards (up to 4) - for key numbers/KPIs
2. Charts (up to 2) - for trends/time-series
3. Tables (up to 3) - for list data

Return ONLY valid JSON in this format:
{{
  "metrics": [
    {{"title": "...", "value": "...", "trend_value": "...", "trend_direction": "up|down"}}
  ],
  "charts": [
    {{"chart_id": "...", "title": "...", "data": [{{"date": "...", "value": 0}}]}}
  ],
  "tables": [
    {{"table_id": "...", "tabs": [...], "columns": [...], "data": [...]}}
  ]
}}
"""
        return prompt

    def _parse_llm_response(
        self, llm_response: str, api_name: str, api_endpoint: str
    ) -> DashboardConfig:
        """Parse LLM JSON response into DashboardConfig"""
        try:
            data = json.loads(llm_response)

            config = DashboardConfig(
                title=f"{api_name} Dashboard", subtitle=f"AI-generated from {api_endpoint}"
            )

            # Add metrics
            for metric in data.get("metrics", []):
                config.add_metric(**metric)

            # Add charts
            for chart in data.get("charts", []):
                config.add_chart(**chart)

            # Add tables
            for table in data.get("tables", []):
                config.add_table(**table)

            return config

        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            raise

    def generate_from_model_with_live_data(
        self, model_class, config_schema: Optional[Dict] = None
    ) -> Dict:
        """
        Generate dashboard from SQLAlchemy model with LIVE CALCULATED metrics

        This is the NEW method that uses real database queries instead of mock data.

        Args:
            model_class: SQLAlchemy model (e.g., BusinessCapability)
            config_schema: Optional configuration:
                {
                    "title": "Custom Title",
                    "metrics": [
                        {
                            "title": "Total Revenue",
                            "field": "annual_cost",
                            "aggregation": "SUM",
                            "filter": "status='active'",
                            "format": "currency"
                        }
                    ],
                    "sections": ["metrics", "charts", "table"]
                }

        Returns:
            DashboardConfig with LIVE calculated metrics
        """
        from sqlalchemy import inspect

        from app import db

        logger.info(f"Generating dashboard for {model_class.__name__} with LIVE data")

        model_name = model_class.__name__
        config_schema = config_schema or {}

        # Create dashboard config
        config = DashboardConfig(
            title=config_schema.get("title", f"{model_name} Dashboard"),
            subtitle=config_schema.get("subtitle", f"Live metrics and analytics for {model_name}"),
        )

        # === LIVE METRICS ===
        # Option 1: Use predefined metrics from schema
        if "metrics" in config_schema:
            for metric_def in config_schema["metrics"]:
                metric = self.metric_calculator.calculate_metric(model_class, metric_def)
                config.add_metric(**metric)

        # Option 2: Auto-generate standard metrics
        else:
            metrics = self.metric_calculator.calculate_metrics_for_model(model_class)
            for metric in metrics[:4]:  # Limit to 4 cards
                config.add_metric(**metric)

        # === LIVE CHARTS ===
        if "charts" not in config_schema.get("exclude_sections", []):
            # Generate trend chart if created_at exists
            if hasattr(model_class, "created_at"):
                chart_data = self._generate_time_series_chart(model_class)
                if chart_data:
                    config.add_chart(**chart_data)

        # === LIVE DATA TABLE ===
        if "table" not in config_schema.get("exclude_sections", []):
            table_data = self._generate_model_table(model_class)
            if table_data:
                config.add_table(**table_data)

        logger.info(
            f"Generated dashboard: {len(config.metrics)} metrics, {len(config.charts)} charts, {len(config.tables)} tables"
        )

        return config.to_dict()

    def _generate_time_series_chart(self, model_class) -> Optional[Dict]:
        """Generate time-series chart from model data"""
        from datetime import datetime, timedelta

        from sqlalchemy import extract, func

        from app import db

        if not hasattr(model_class, "created_at"):
            return None

        try:
            # Get data for last 90 days
            ninety_days_ago = datetime.now() - timedelta(days=90)

            # Query: Group by date, count records
            results = (
                db.session.query(
                    func.date(model_class.created_at).label("date"),
                    func.count(model_class.id).label("count"),
                )
                .filter(model_class.created_at >= ninety_days_ago)
                .group_by(func.date(model_class.created_at))
                .order_by(func.date(model_class.created_at))
                .all()
            )

            # Convert to chart format
            chart_data = []
            for row in results:
                chart_data.append({"date": row.date.strftime("%Y-%m-%d"), "value": row.count})

            # Fill in missing dates with 0
            if chart_data:
                all_dates = []
                for i in range(90):
                    date = (datetime.now() - timedelta(days=89 - i)).date()
                    all_dates.append(date)

                # Create complete dataset
                complete_data = []
                existing_dates = {
                    datetime.strptime(d["date"], "%Y-%m-%d").date(): d["value"] for d in chart_data
                }

                for date in all_dates:
                    complete_data.append(
                        {"date": date.strftime("%Y-%m-%d"), "value": existing_dates.get(date, 0)}
                    )

                chart_data = complete_data

            return {
                "chart_id": f"{model_class.__name__}_trend",
                "title": f"{model_class.__name__} Growth Trend",
                "subtitle": "Records created over last 90 days",
                "data": chart_data,
                "time_ranges": [
                    {"id": "90d", "label": "Last 90 days"},
                    {"id": "30d", "label": "Last 30 days"},
                    {"id": "7d", "label": "Last 7 days"},
                ],
            }

        except Exception as e:
            logger.warning(f"Could not generate time-series chart: {e}")
            return None

    def _generate_model_table(
        self, model_class, limit: int = 100, detail_url_pattern: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate data table from model with ellipses menu and drawer modal

        Args:
            model_class: SQLAlchemy model
            limit: Max records to fetch
            detail_url_pattern: URL pattern for detail pages (e.g., '/business-capabilities/{id}')
                               If None, will auto-generate from model tablename
        """
        from sqlalchemy import inspect

        from app import db

        try:
            # Get model columns
            inspector = inspect(model_class)
            columns = []

            # Add select column (checkbox)
            columns.append(
                {
                    "id": "select",
                    "label": "",
                    "type": "checkbox",
                    "sortable": False,
                    "visible": True,
                }
            )

            for column in inspector.columns:
                # Skip large text fields and internal IDs in visible columns
                if column.name in ["description", "notes"] or str(column.type) == "TEXT":
                    continue
                # Skip id from visible columns but keep it in data
                if column.name == "id":
                    continue

                columns.append(
                    {
                        "id": column.name,
                        "label": column.name.replace("_", " ").title(),
                        "type": self._map_column_type_to_table_type(column),
                        "sortable": True,
                        "visible": True,
                    }
                )

            # Limit columns to first 8 (excluding select and actions)
            columns = columns[:9]

            # Add actions column (ellipses menu)
            columns.append(
                {
                    "id": "actions",
                    "label": "",
                    "type": "actions",
                    "sortable": False,
                    "visible": True,
                }
            )

            # Fetch actual data
            records = db.session.query(model_class).limit(limit).all()

            # Auto-generate detail URL pattern if not provided
            if not detail_url_pattern:
                # Convert tablename to URL-friendly format
                # e.g., 'business_capability' -> '/business-capabilities/{id}'
                table_name = model_class.__tablename__

                # Smart pluralization
                if table_name.endswith("s"):
                    url_name = table_name
                elif table_name.endswith("y"):
                    # Change 'y' to 'ies' (e.g., capability -> capabilities)
                    url_name = table_name[:-1] + "ies"
                else:
                    url_name = table_name + "s"

                url_name = url_name.replace("_", "-")
                detail_url_pattern = f"/{url_name}/{{id}}"

            # Convert to dicts
            data = []
            for record in records:
                row = {"id": record.id}  # CRITICAL: Always include id for row identification

                # Add view_url for "View" button in actions menu
                row["view_url"] = detail_url_pattern.format(id=record.id)

                for col in columns:
                    if col["id"] in ["select", "actions"]:
                        continue  # These are rendered by JavaScript

                    value = getattr(record, col["id"], None)
                    if isinstance(value, datetime):
                        row[col["id"]] = value.strftime("%Y-%m-%d %H:%M")
                    elif value is None:
                        row[col["id"]] = "-"
                    else:
                        row[col["id"]] = str(value)

                data.append(row)

            return {
                "table_id": f"{model_class.__name__}_table",
                "tabs": [{"id": "outline", "label": "All Records", "badge": str(len(records))}],
                "columns": columns,
                "data": data,
                "show_customize": True,
                "show_add_section": False,  # Disable for auto-generated tables
                "api_endpoint": f"/api/{model_class.__tablename__}",
                "model_name": model_class.__name__
                # Note: detail_url_pattern stored in row data as 'view_url'
            }

        except Exception as e:
            logger.warning(f"Could not generate model table: {e}")
            return None

    def _map_column_type_to_table_type(self, column) -> str:
        """Map SQLAlchemy column type to table column type"""
        column_type = str(column.type).upper()

        if "INT" in column_type or "NUMERIC" in column_type or "FLOAT" in column_type:
            return "number"
        elif "BOOL" in column_type:
            return "badge"
        elif "DATE" in column_type or "TIME" in column_type:
            return "text"
        else:
            return "text"

    def generate_detail_page(self, model_class, record_id, list_url: str) -> Dict:
        """
        Generate detail page configuration for a single record

        Args:
            model_class: SQLAlchemy model
            record_id: ID of the record to display
            list_url: URL to return to list view

        Returns:
            Dictionary with all detail page data
        """
        import traceback
        from datetime import datetime

        from sqlalchemy import inspect

        from app import db

        logger.info(f"=== generate_detail_page START ===")
        logger.info(f"Model: {model_class.__name__}, ID: {record_id}")

        try:
            # Fetch the record
            logger.info(f"Fetching record from database...")
            record = db.session.query(model_class).get(record_id)
            if not record:
                raise ValueError(f"{model_class.__name__} with ID {record_id} not found")
            logger.info(f"Record found: {record}")

            # Get model columns
            logger.info(f"Inspecting model columns...")
            inspector = inspect(model_class)
            logger.info(f"Inspector created, columns count: {len(list(inspector.columns))}")
        except Exception as e:
            logger.error(f"Error in initial setup: {e}")
            logger.error(traceback.format_exc())
            raise

        # Organize fields into sections
        sections = []

        # Basic Information Section
        basic_fields = []
        logger.info(f"Processing {len(list(inspector.columns))} columns...")

        for column in inspector.columns:
            if column.name in ["id", "created_at", "updated_at"]:
                continue  # These go in the header

            try:
                logger.info(f"  Processing column: {column.name}")
                field_value = getattr(record, column.name, None)
                logger.info(f"    Value type: {type(field_value)}")

                # Convert non-serializable types to strings
                if callable(field_value):
                    # Skip methods/callables
                    logger.warning(f"    Skipping callable field: {column.name}")
                    continue

                # Determine field type BEFORE converting to string
                # (so we can inspect original type)
                field_type = self._determine_field_type(column, field_value)
                logger.info(f"    Field type determined: {field_type}")

                # Now convert to template-safe types
                if isinstance(field_value, datetime):
                    field_value = field_value.strftime("%Y-%m-%d %H:%M:%S")
                elif field_value is None:
                    field_value = ""
                elif not isinstance(field_value, (str, int, float, bool)):
                    # Convert any other types (like SQLAlchemy objects) to string
                    field_value = str(field_value)

                logger.info(
                    f"    Final value: {field_value[:50] if isinstance(field_value, str) and len(field_value) > 50 else field_value}"
                )

                basic_fields.append(
                    {
                        "name": column.name,
                        "label": column.name.replace("_", " ").title(),
                        "value": field_value,
                        "type": field_type,
                    }
                )
            except Exception as e:
                logger.error(f"    ERROR processing field {column.name}: {str(e)}")
                logger.error(traceback.format_exc())
                continue

        logger.info(f"Processed {len(basic_fields)} fields successfully")

        # Split into sections (max 8 fields per section)
        chunk_size = 8
        for i in range(0, len(basic_fields), chunk_size):
            section_fields = basic_fields[i : i + chunk_size]
            section_number = (i // chunk_size) + 1

            sections.append(
                {
                    "title": f"Details ({section_number})"
                    if len(basic_fields) > chunk_size
                    else "Details",
                    "description": f"{model_class.__name__} information",
                    "fields": section_fields,
                }
            )

        # Get related records (relationships) as interactive data tables
        related_records = []
        logger.info(f"Processing relationships for {model_class.__name__}...")
        logger.info(f"Found {len(list(inspector.relationships))} relationships")

        for relationship in inspector.relationships:
            try:
                logger.info(f"  Checking relationship: {relationship.key}")
                related_items = getattr(record, relationship.key, None)
                logger.info(f"    Related items type: {type(related_items)}")

                if related_items is not None:
                    # Handle both list and single relationships
                    if hasattr(related_items, "__iter__") and not isinstance(related_items, str):
                        items_list = list(related_items)
                        logger.info(f"    Items count: {len(items_list)}")

                        if not items_list:
                            logger.info(f"    Skipping empty relationship: {relationship.key}")
                            continue  # Skip empty relationships

                        # Get the related model class
                        related_model = relationship.mapper.class_
                        logger.info(f"    Related model: {related_model.__name__}")

                        # Generate data table configuration for this relationship
                        table_config = self._generate_related_table(
                            related_model, items_list, relationship.key
                        )

                        if table_config:
                            logger.info(f"    ✓ Added table config for {relationship.key}")
                            related_records.append(table_config)
                        else:
                            logger.warning(
                                f"    Failed to generate table config for {relationship.key}"
                            )

            except Exception as e:
                logger.error(f"  ERROR processing relationship {relationship.key}: {e}")
                logger.error(traceback.format_exc())
                continue

        logger.info(f"Total related records tables: {len(related_records)}")

        # Convert record to safe dictionary for template
        logger.info(f"Creating safe record dictionary...")
        try:
            created_at = getattr(record, "created_at", None)
            updated_at = getattr(record, "updated_at", None)

            # Format dates safely (handle both datetime objects and strings)
            def format_date(date_value):
                if date_value is None:
                    return None
                if isinstance(date_value, str):
                    return date_value  # Already formatted
                if hasattr(date_value, "strftime"):
                    return date_value.strftime("%B %d, %Y")
                return str(date_value)

            record_dict = {
                "id": record.id,
                "name": getattr(record, "name", f"{model_class.__name__} #{record.id}"),
                "status": getattr(record, "status", None),
                "description": getattr(record, "description", None),
                "created_at": format_date(created_at),
                "updated_at": format_date(updated_at),
            }
            logger.info(f"Record dict created: {list(record_dict.keys())}")
        except Exception as e:
            logger.error(f"Error creating record dict: {e}")
            logger.error(traceback.format_exc())
            raise

        logger.info(f"Building final config dictionary...")
        try:
            result = {
                "record": record_dict,
                "model_name": model_class.__name__,
                "sections": sections,
                "related_records": related_records,
                "related_count": sum(r["count"] for r in related_records),
                "list_url": list_url,
                "delete_url": f"/api/{model_class.__tablename__}/{record_id}",
            }
            logger.info(f"=== generate_detail_page COMPLETE ===")
            return result
        except Exception as e:
            logger.error(f"Error building final config: {e}")
            logger.error(traceback.format_exc())
            raise

    def _get_plural_tablename(self, tablename: str) -> str:
        """Convert table name to URL-friendly plural format

        Args:
            tablename: Original table name (e.g., 'business_capability')

        Returns:
            Pluralized, URL-friendly name (e.g., 'business-capabilities')
        """
        # Smart pluralization
        if tablename.endswith("s"):
            url_name = tablename
        elif tablename.endswith("y"):
            # Change 'y' to 'ies' (e.g., capability -> capabilities)
            url_name = tablename[:-1] + "ies"
        else:
            url_name = tablename + "s"

        # Convert underscores to hyphens for URLs
        return url_name.replace("_", "-")

    def _generate_related_table(
        self, model_class, items_list: list, relationship_name: str
    ) -> Optional[Dict]:
        """Generate data table configuration for related records

        Args:
            model_class: SQLAlchemy model class for related records
            items_list: List of related record instances
            relationship_name: Name of the relationship (for display)

        Returns:
            Dictionary with table configuration compatible with ShadcnDataTableExact
        """
        import traceback
        from datetime import datetime

        from sqlalchemy import inspect

        try:
            if not items_list:
                return None

            inspector = inspect(model_class)

            # Generate columns from model
            columns = []

            # Add select column
            columns.append({"id": "select", "label": "", "sortable": False})

            # Add data columns
            for column in inspector.columns:
                if column.name == "id":
                    continue  # Skip ID column

                col_config = {
                    "id": column.name,
                    "label": column.name.replace("_", " ").title(),
                    "sortable": True,
                }

                # Determine column type
                if column.name == "status":
                    col_config["type"] = "badge"

                columns.append(col_config)

            # Add actions column
            columns.append({"id": "actions", "label": "", "sortable": False})

            # Generate data rows
            data = []
            plural_tablename = self._get_plural_tablename(model_class.__tablename__)

            for item in items_list:
                row = {"id": item.id}

                # Add view_url for the "View" action
                row["view_url"] = f"/{plural_tablename}/{item.id}"

                for column in inspector.columns:
                    if column.name == "id":
                        continue

                    value = getattr(item, column.name, None)

                    # Convert to template-safe types
                    if isinstance(value, datetime):
                        row[column.name] = value.strftime("%Y-%m-%d")
                    elif value is None:
                        row[column.name] = ""
                    elif not isinstance(value, (str, int, float, bool)):
                        row[column.name] = str(value)
                    else:
                        row[column.name] = value

                data.append(row)

            # Generate unique table ID
            table_id = f"{relationship_name.lower()}_table"

            return {
                "relationship_name": relationship_name,
                "title": relationship_name.replace("_", " ").title(),
                "count": len(items_list),
                "table_id": table_id,
                "columns": columns,
                "data": data,
                "api_endpoint": f"/api/{model_class.__tablename__}",
                "model_name": model_class.__name__,
            }

        except Exception as e:
            logger.error(f"Error generating related table for {relationship_name}: {e}")
            logger.error(traceback.format_exc())
            return None

    def _determine_field_type(self, column, value) -> str:
        """Determine display type for a field

        Note: This is called BEFORE value conversion to string,
        so we can inspect the original value type.
        """
        from datetime import datetime

        column_type = str(column.type).upper()

        # Check column properties first (more reliable than value inspection)
        if column.name == "status" or "status" in column.name:
            return "badge"
        elif "BOOL" in column_type:
            return "boolean"
        elif "INT" in column_type or "NUMERIC" in column_type or "FLOAT" in column_type:
            if "cost" in column.name or "price" in column.name or "revenue" in column.name:
                return "currency"
            return "number"
        elif "DATE" in column_type and "TIME" in column_type:
            return "datetime"
        elif "DATE" in column_type:
            return "date"
        elif "TEXT" in column_type:
            return "textarea"
        elif column.name.endswith("_url") or column.name.startswith("url_"):
            return "link"
        else:
            return "text"

    def get_export_data(self, dashboard_type: str) -> List[Dict]:
        """
        Get export data for a dashboard type.

        Args:
            dashboard_type: Type of dashboard (e.g., 'applications', 'capabilities')

        Returns:
            List of dictionaries with export data
        """
        from app import db
        from app.models.application_layer import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability

        data = []

        if dashboard_type == "applications":
            apps = db.session.query(ApplicationComponent).limit(1000).all()
            for app in apps:
                data.append(
                    {
                        "id": app.id,
                        "name": app.name or "",
                        "type": app.component_type or "",
                        "category": app.application_category or "",
                        "status": app.deployment_status or "",
                        "owner": app.business_owner or "",
                        "domain": app.business_domain or "",
                        "criticality": app.business_criticality or "",
                        "created_at": app.created_at.strftime("%Y-%m-%d")
                        if hasattr(app, "created_at") and app.created_at
                        else "",
                    }
                )
        elif dashboard_type == "capabilities":
            caps = db.session.query(BusinessCapability).limit(1000).all()
            for cap in caps:
                data.append(
                    {
                        "id": cap.id,
                        "name": cap.name or "",
                        "level": getattr(cap, "level", ""),
                        "status": getattr(cap, "status", ""),
                        "owner": getattr(cap, "owner", ""),
                        "created_at": cap.created_at.strftime("%Y-%m-%d")
                        if hasattr(cap, "created_at") and cap.created_at
                        else "",
                    }
                )
        else:
            # Generic fallback
            data = [{"message": f"No export data available for {dashboard_type}"}]

        return data

    def generate_csv(self, data: List[Dict]) -> io.BytesIO:
        """
        Generate CSV file from data.

        Args:
            data: List of dictionaries to export

        Returns:
            BytesIO object with CSV content
        """
        import csv

        output = io.StringIO()

        if not data:
            writer = csv.writer(output)
            writer.writerow(["No data available"])
        elif len(data) > 0 and isinstance(data[0], dict):
            # Dict data - use DictWriter
            fieldnames = list(data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        elif len(data) > 0:
            # List data - use regular writer
            writer = csv.writer(output)
            writer.writerows(data)
        else:
            # Empty list
            writer = csv.writer(output)
            writer.writerow(["No data available"])

        output.seek(0)
        csv_content = output.getvalue()
        # Convert to BytesIO for send_file
        csv_bytes = io.BytesIO(csv_content.encode("utf-8"))
        csv_bytes.seek(0)
        return csv_bytes

    def generate_excel(self, data: List[Dict]) -> io.BytesIO:
        """
        Generate Excel file from data.

        Args:
            data: List of dictionaries to export

        Returns:
            BytesIO object with Excel content
        """
        try:
            import openpyxl
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active

            if not data:
                ws.append(["No data available"])
            elif isinstance(data[0], dict):
                # Write headers
                headers = list(data[0].keys())
                ws.append(headers)

                # Write data rows
                for row in data:
                    ws.append([row.get(key, "") for key in headers])
            else:
                # List data
                for row in data:
                    ws.append(row if isinstance(row, list) else [row])

            # Save to BytesIO
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output

        except ImportError:
            # Fallback to CSV if openpyxl not available
            logger.warning("openpyxl not available, falling back to CSV")
            return self.generate_csv(data)
