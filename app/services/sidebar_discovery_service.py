"""
Sidebar Discovery Service

Discovers and maps sidebar parent items from various sources including
database, YAML config, and template analysis. Used by the autonomous
adversarial orchestrator to identify review targets.
"""

import logging
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum

from app.models.sidebar import SidebarMenu, SidebarSection, SidebarItem
from app import db

logger = logging.getLogger(__name__)


class SidebarSource(Enum):
    DATABASE = "database"
    YAML_CONFIG = "yaml_config"
    TEMPLATE_SCAN = "template_scan"
    MANUAL = "manual"


@dataclass
class DiscoveredSidebarItem:
    """A discovered sidebar parent item ready for adversarial review"""
    id: str
    name: str
    display_name: str
    icon: str
    url: str
    route_prefix: str
    source: SidebarSource
    priority: int = 50  # Lower = higher priority
    children_count: int = 0
    has_routes: bool = False
    has_templates: bool = False
    template_paths: List[str] = field(default_factory=list)
    route_files: List[str] = field(default_factory=list)
    service_files: List[str] = field(default_factory=list)
    review_status: str = "not_reviewed"
    last_reviewed: Optional[str] = None


class SidebarDiscoveryService:
    """
    Discovers sidebar parent items from multiple sources.
    
    Primary sources:
    1. Database (SidebarMenu model)
    2. YAML config files
    3. Template directory scanning
    4. Route file analysis
    """
    
    # Known sidebar parent items in the project
    KNOWN_PARENT_ITEMS = [
        {
            "id": "vendor-management",
            "name": "Vendor Management",
            "icon": "Building2",
            "url": "/vendors",
            "route_prefix": "/vendors",
            "priority": 30,
        },
        {
            "id": "solutions-management",
            "name": "Solutions Management",
            "icon": "Lightbulb",
            "url": "/solutions",
            "route_prefix": "/solutions",
            "priority": 25,
        },
        {
            "id": "application-portfolio",
            "name": "Application Portfolio",
            "icon": "LayoutGrid",
            "url": "/applications",
            "route_prefix": "/applications",
            "priority": 20,
        },
        {
            "id": "duplicate-detection",
            "name": "Duplicate Detection",
            "icon": "CopyX",
            "url": "/duplicates",
            "route_prefix": "/duplicates",
            "priority": 35,
        },
        {
            "id": "architecture-review",
            "name": "Architecture Review Board",
            "icon": "ClipboardCheck",
            "url": "/arb",
            "route_prefix": "/arb",
            "priority": 40,
        },
        {
            "id": "adm-kanban",
            "name": "ADM Kanban",
            "icon": "Kanban",
            "url": "/adm-kanban",
            "route_prefix": "/adm-kanban",
            "priority": 45,
        },
        {
            "id": "archimate-crud",
            "name": "ArchiMate CRUD",
            "icon": "Network",
            "url": "/archimate-crud",
            "route_prefix": "/archimate-crud",
            "priority": 50,
        },
        {
            "id": "batch-import",
            "name": "Batch Import",
            "icon": "Upload",
            "url": "/batch-import",
            "route_prefix": "/batch-import",
            "priority": 55,
        },
        {
            "id": "ai-chat",
            "name": "AI Chat",
            "icon": "Bot",
            "url": "/ai-chat",
            "route_prefix": "/ai-chat",
            "priority": 60,
        },
        {
            "id": "auto-dashboard",
            "name": "Auto Dashboard",
            "icon": "Gauge",
            "url": "/auto-dashboard",
            "route_prefix": "/auto-dashboard",
            "priority": 65,
        },
        {
            "id": "capabilities",
            "name": "Capabilities",
            "icon": "Layers",
            "url": "/capabilities",
            "route_prefix": "/capabilities",
            "priority": 70,
        },
        {
            "id": "maturity-assessment",
            "name": "Maturity Assessment",
            "icon": "TrendingUp",
            "url": "/maturity",
            "route_prefix": "/maturity",
            "priority": 75,
        },
        {
            "id": "tech-debt",
            "name": "Technical Debt",
            "icon": "AlertTriangle",
            "url": "/tech-debt",
            "route_prefix": "/tech-debt",
            "priority": 80,
        },
    ]
    
    # Route file mappings
    ROUTE_FILE_MAP = {
        "/vendors": ["vendor_routes.py", "vendor_api_routes.py"],
        "/solutions": ["solution_design_routes.py", "solution_architect_routes.py", "solution_composer_routes.py"],
        "/applications": ["unified_applications_routes.py", "applications_routes.py"],
        "/duplicates": ["unified_duplicate_routes.py", "dedupe_routes.py"],
        "/arb": ["arb_routes.py", "arb_api_routes.py"],
        "/adm-kanban": ["adm_kanban_routes.py", "adm_kanban_api.py"],
        "/archimate-crud": ["archimate_crud_routes.py"],
        "/batch-import": ["batch_import_routes.py", "unified_applications_routes.py"],
        "/ai-chat": ["ai_chat_routes.py"],
        "/auto-dashboard": ["dashboard_routes.py", "auto_dashboard_routes.py"],
        "/capabilities": ["capability_routes.py"],
        "/maturity": ["maturity_routes.py"],
        "/tech-debt": ["tech_debt_routes.py"],
    }
    
    # Template directory mappings
    TEMPLATE_DIR_MAP = {
        "/vendors": "vendors/",
        "/solutions": "solutions/",
        "/applications": "applications/",
        "/duplicates": "duplicates/",
        "/arb": "arb/",
        "/adm-kanban": "adm_kanban/",
        "/archimate-crud": "archimate_crud/",
        "/batch-import": "batch_import/",
        "/ai-chat": "ai_chat/",
        "/auto-dashboard": "auto_dashboard/",
        "/capabilities": "capabilities/",
        "/maturity": "maturity/",
        "/tech-debt": "tech_debt/",
    }
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.routes_dir = self.project_root / "app" / "routes"
        self.templates_dir = self.project_root / "app" / "templates"
        self.services_dir = self.project_root / "app" / "services"
        
    def discover_all(self) -> List[DiscoveredSidebarItem]:
        """Discover all sidebar items from all sources."""
        items = []
        discovered_ids: Set[str] = set()
        
        # 1. Discover from known items (primary source)
        for item_data in self.KNOWN_PARENT_ITEMS:
            item = self._create_from_known(item_data)
            items.append(item)
            discovered_ids.add(item.id)
        
        # 2. Discover from database if available
        try:
            db_items = self._discover_from_database()
            for item in db_items:
                if item.id not in discovered_ids:
                    items.append(item)
                    discovered_ids.add(item.id)
        except Exception as e:
            logger.warning(f"Database discovery failed: {e}")
        
        # 3. Discover from YAML config
        yaml_items = self._discover_from_yaml()
        for item in yaml_items:
            if item.id not in discovered_ids:
                items.append(item)
                discovered_ids.add(item.id)
        
        # 4. Enrich with file paths
        items = [self._enrich_with_files(item) for item in items]
        
        # Sort by priority
        items.sort(key=lambda x: x.priority)
        
        logger.info(f"Discovered {len(items)} sidebar parent items")
        return items
    
    def _create_from_known(self, data: Dict) -> DiscoveredSidebarItem:
        """Create a discovered item from known data."""
        return DiscoveredSidebarItem(
            id=data["id"],
            name=data["name"],
            display_name=data["name"],
            icon=data.get("icon", "Circle"),
            url=data["url"],
            route_prefix=data["route_prefix"],
            source=SidebarSource.MANUAL,
            priority=data.get("priority", 50)
        )
    
    def _discover_from_database(self) -> List[DiscoveredSidebarItem]:
        """Discover items from the database."""
        items = []
        
        try:
            # Query sidebar menu items that are parents
            sidebar_items = SidebarItem.query.filter_by(is_parent=True, is_active=True).all()
            
            for item in sidebar_items:
                discovered = DiscoveredSidebarItem(
                    id=f"db-{item.id}",
                    name=item.name,
                    display_name=item.display_name or item.name,
                    icon=item.icon or "Circle",
                    url=item.url or "#",
                    route_prefix=item.url or "",
                    source=SidebarSource.DATABASE,
                    priority=item.sort_order or 50,
                    children_count=len(item.children) if item.children else 0
                )
                items.append(discovered)
                
        except Exception as e:
            logger.warning(f"Could not query database: {e}")
            
        return items
    
    def _discover_from_yaml(self) -> List[DiscoveredSidebarItem]:
        """Discover items from YAML configuration files."""
        items = []
        
        # Look for sidebar config files
        config_paths = [
            self.project_root / "config" / "sidebar.yaml",
            self.project_root / "config" / "sidebar_menu.yaml",
            self.project_root / ".cursor" / "sidebar.yaml",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    for section in config.get('sections', []):
                        for item_data in section.get('items', []):
                            if item_data.get('type') == 'parent' or item_data.get('children'):
                                item = DiscoveredSidebarItem(
                                    id=item_data.get('id', f"yaml-{len(items)}"),
                                    name=item_data.get('name', 'Unknown'),
                                    display_name=item_data.get('display_name', item_data.get('name', 'Unknown')),
                                    icon=item_data.get('icon', 'Circle'),
                                    url=item_data.get('url', '#'),
                                    route_prefix=item_data.get('url', ''),
                                    source=SidebarSource.YAML_CONFIG,
                                    priority=item_data.get('priority', 50),
                                    children_count=len(item_data.get('children', []))
                                )
                                items.append(item)
                                
                except Exception as e:
                    logger.warning(f"Could not load {config_path}: {e}")
                    
        return items
    
    def _enrich_with_files(self, item: DiscoveredSidebarItem) -> DiscoveredSidebarItem:
        """Enrich item with associated file paths."""
        # Find route files
        route_files = self.ROUTE_FILE_MAP.get(item.route_prefix, [])
        for filename in route_files:
            route_path = self.routes_dir / filename
            if route_path.exists():
                item.route_files.append(str(route_path))
                item.has_routes = True
        
        # Find templates
        template_dir = self.TEMPLATE_DIR_MAP.get(item.route_prefix)
        if template_dir:
            template_path = self.templates_dir / template_dir
            if template_path.exists():
                item.has_templates = True
                # Find all HTML files in the directory
                for template_file in template_path.rglob("*.html"):
                    item.template_paths.append(str(template_file))
        
        # Find service files (heuristic: match by name)
        service_patterns = [
            f"{item.id.replace('-', '_')}_service.py",
            f"{item.id.replace('-', '')}_service.py",
        ]
        for pattern in service_patterns:
            service_path = self.services_dir / pattern
            if service_path.exists():
                item.service_files.append(str(service_path))
        
        return item
    
    def get_item_by_id(self, item_id: str) -> Optional[DiscoveredSidebarItem]:
        """Get a specific sidebar item by ID."""
        all_items = self.discover_all()
        for item in all_items:
            if item.id == item_id:
                return item
        return None
    
    def get_items_by_status(self, status: str) -> List[DiscoveredSidebarItem]:
        """Get items filtered by review status."""
        all_items = self.discover_all()
        return [item for item in all_items if item.review_status == status]
    
    def get_next_unreviewed(self) -> Optional[DiscoveredSidebarItem]:
        """Get the next unreviewed item by priority."""
        unreviewed = self.get_items_by_status("not_reviewed")
        if unreviewed:
            return min(unreviewed, key=lambda x: x.priority)
        return None
    
    def update_review_status(self, item_id: str, status: str, timestamp: Optional[str] = None):
        """Update the review status of an item."""
        # This would update the persistent store
        # For now, just log it
        logger.info(f"Updated {item_id} status to {status}")
        
    def get_review_statistics(self) -> Dict:
        """Get statistics about sidebar item reviews."""
        all_items = self.discover_all()
        
        return {
            "total": len(all_items),
            "with_routes": sum(1 for i in all_items if i.has_routes),
            "with_templates": sum(1 for i in all_items if i.has_templates),
            "not_reviewed": sum(1 for i in all_items if i.review_status == "not_reviewed"),
            "reviewed": sum(1 for i in all_items if i.review_status == "reviewed"),
            "by_priority": {
                "high (<=30)": sum(1 for i in all_items if i.priority <= 30),
                "medium (31-60)": sum(1 for i in all_items if 30 < i.priority <= 60),
                "low (>60)": sum(1 for i in all_items if i.priority > 60),
            }
        }


# Singleton instance
_discovery_service: Optional[SidebarDiscoveryService] = None


def get_sidebar_discovery_service() -> SidebarDiscoveryService:
    """Get or create the singleton sidebar discovery service."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = SidebarDiscoveryService()
    return _discovery_service
