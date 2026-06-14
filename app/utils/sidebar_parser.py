"""
Sidebar Template Parser Utility

Extracts menu structure from admin_sidebar.html for feature flag management.
Parses hierarchical menu sections, parent menus, and submenu items.
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional

from flask import current_app


@dataclass
class SidebarLink:
    """Represents a single sidebar link."""

    text: str
    href: str
    icon: Optional[str] = None
    endpoint: Optional[str] = None
    is_active_check: Optional[str] = None

    @property
    def feature_key(self) -> str:
        """Generate a feature flag key from the text."""
        return self.text.lower().replace(" ", "_").replace("-", "_")


@dataclass
class SidebarSection:
    """Represents a top-level section (Home, Application, Architecture, etc.)."""

    title: str
    links: List[SidebarLink]
    submenus: List["SidebarSubmenu"]

    @property
    def feature_key(self) -> str:
        """Generate a feature flag key from the section title."""
        return f"section_{self.title.lower().replace(' ', '_')}"


@dataclass
class SidebarSubmenu:
    """Represents a collapsible submenu (Applications Management, Vendor Management, etc.)."""

    title: str
    icon: Optional[str]
    parent_section: str
    links: List[SidebarLink]

    @property
    def feature_key(self) -> str:
        """Generate a feature flag key from the submenu title."""
        return self.title.lower().replace(" ", "_").replace("-", "_")


class SidebarParser:
    """Parser for extracting menu structure from admin_sidebar.html template."""

    def __init__(self, template_path: Optional[str] = None):
        """
        Initialize the sidebar parser.

        Args:
            template_path: Path to admin_sidebar.html. If None, uses default location.
        """
        self.template_path = template_path
        self.sections: List[SidebarSection] = []

    def get_template_path(self) -> str:
        """Get the path to admin_sidebar.html template."""
        if self.template_path:
            return self.template_path

        # Use Flask app's template folder
        try:
            template_folder = current_app.template_folder
            return os.path.join(template_folder, "components", "admin_sidebar.html")
        except RuntimeError:
            # Fallback for when not in app context
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            return os.path.join(base_dir, "app", "templates", "components", "admin_sidebar.html")

    def parse(self) -> List[SidebarSection]:
        """
        Parse the sidebar template and extract all menu items.

        Returns:
            List of SidebarSection objects with hierarchical structure.
        """
        template_path = self.get_template_path()

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Sidebar template not found: {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.sections = []
        self._parse_sections(content)

        return self.sections

    def _parse_sections(self, content: str):
        """Parse top-level sections from template content."""
        # Pattern to match section headers like "Home", "Application", "Architecture"
        section_pattern = r"<h2[^>]*>\s*([^<]+)\s*</h2>"

        # Find all section markers
        section_matches = list(re.finditer(section_pattern, content))

        for i, match in enumerate(section_matches):
            section_title = match.group(1).strip()

            # Get content between this section and the next one
            start_pos = match.end()
            end_pos = (
                section_matches[i + 1].start() if i + 1 < len(section_matches) else len(content)
            )
            section_content = content[start_pos:end_pos]

            # Parse submenus and direct links in this section
            submenus = self._parse_submenus(section_content, section_title)
            direct_links = self._parse_direct_links(section_content)

            section = SidebarSection(title=section_title, links=direct_links, submenus=submenus)

            self.sections.append(section)

    def _parse_submenus(self, content: str, parent_section: str) -> List[SidebarSubmenu]:
        """Parse collapsible submenus from section content."""
        submenus = []

        # Pattern to match submenu buttons with chevron icons
        # Example: <button @click="toggleArchSection('strategic')" ...>
        #              <i data-lucide="target" ...></i>
        #              <span>Strategic Planning</span>

        # Find submenu button blocks
        button_pattern = r'<button[^>]*@click="[^"]*\([^)]*\)"[^>]*>(.*?)</button>'
        button_matches = re.finditer(button_pattern, content, re.DOTALL)

        for button_match in button_matches:
            button_html = button_match.group(1)

            # Extract icon
            icon_match = re.search(r'data-lucide="([^"]+)"', button_html)
            icon = icon_match.group(1) if icon_match else None

            # Skip chevron icons - they're for expanding
            if icon == "chevron-right":
                icon_match = re.search(
                    r'data-lucide="([^"]+)".*?data-lucide="([^"]+)"', button_html
                )
                icon = icon_match.group(2) if icon_match else None

            # Extract submenu title from span
            title_match = re.search(r"<span[^>]*>(.*?)</span>", button_html)
            if not title_match:
                continue

            title = title_match.group(1).strip()

            # Find the corresponding submenu content div (x-show directive)
            # It appears right after the button
            submenu_start = button_match.end()
            submenu_pattern = r"<div x-show=[^>]*>(.*?)</div>\s*</div>"
            submenu_match = re.search(
                submenu_pattern, content[submenu_start : submenu_start + 5000], re.DOTALL
            )

            if submenu_match:
                submenu_content = submenu_match.group(1)
                links = self._parse_links_from_content(submenu_content)

                submenu = SidebarSubmenu(
                    title=title, icon=icon, parent_section=parent_section, links=links
                )
                submenus.append(submenu)

        return submenus

    def _parse_direct_links(self, content: str) -> List[SidebarLink]:
        """Parse direct links (not in submenus) from content."""
        links = []

        # Find all <a> tags in the content
        link_pattern = r'<a\s+href="{{[^}]*url_for\([\'"]([^\'"]*)[\'"]\)[^}]*}}"[^>]*>(.*?)</a>'
        link_matches = re.finditer(link_pattern, content, re.DOTALL)

        for link_match in link_matches:
            endpoint = link_match.group(1)
            link_html = link_match.group(2)

            # Check if this link is inside an x-show div (submenu)
            # Get the position of the link
            link_start = link_match.start()

            # Look backwards for the nearest x-show div
            before_link = content[:link_start]
            x_show_match = re.search(r"<div[^>]*x-show=[^>]*>", before_link)

            if x_show_match:
                # Check if there's a closing </div> between the x-show and the link
                after_x_show = before_link[x_show_match.end() :]
                # If there are more opening divs than closing divs, it's inside
                opening_divs = after_x_show.count("<div")
                closing_divs = after_x_show.count("</div>")
                if opening_divs >= closing_divs:
                    # This link is inside an x-show div, skip it (it's in a submenu)
                    continue

            # This is a direct link, parse it
            # Extract icon
            icon_match = re.search(r'data-lucide="([^"]+)"', link_html)
            icon = icon_match.group(1) if icon_match else None

            # Extract text from span
            text_match = re.search(r"<span[^>]*>(.*?)</span>", link_html)
            if not text_match:
                continue

            text = text_match.group(1).strip()

            # Extract the href for display
            href = f"/admin/{endpoint.replace('.', '/')}" if endpoint else ""

            # Extract active check condition if present
            active_check = None
            if "request.endpoint ==" in content:
                check_match = re.search(
                    rf"request\.endpoint == '{re.escape(endpoint)}'",
                    content[max(0, link_match.start() - 500) : link_match.end()],
                )
                if check_match:
                    active_check = check_match.group(0)

            link = SidebarLink(
                text=text, href=href, icon=icon, endpoint=endpoint, is_active_check=active_check
            )
            links.append(link)

        return links

    def _parse_links_from_content(self, content: str) -> List[SidebarLink]:
        """Parse <a> tags from content and extract link information."""
        links = []

        # Pattern to match <a href="{{ url_for(...) }}" ...>
        link_pattern = r'<a\s+href="{{[^}]*url_for\([\'"]([^\'"]*)[\'"]\)[^}]*}}"[^>]*>(.*?)</a>'
        link_matches = re.finditer(link_pattern, content, re.DOTALL)

        for link_match in link_matches:
            endpoint = link_match.group(1)
            link_html = link_match.group(2)

            # Extract icon
            icon_match = re.search(r'data-lucide="([^"]+)"', link_html)
            icon = icon_match.group(1) if icon_match else None

            # Extract text from span
            text_match = re.search(r"<span[^>]*>(.*?)</span>", link_html)
            if not text_match:
                continue

            text = text_match.group(1).strip()

            # Extract the href for display (we'll use endpoint for actual routing)
            href = f"/admin/{endpoint.replace('.', '/')}" if endpoint else ""

            # Extract active check condition if present
            active_check = None
            if "request.endpoint ==" in content:
                check_match = re.search(
                    rf"request\.endpoint == '{re.escape(endpoint)}'",
                    content[max(0, link_match.start() - 500) : link_match.end()],
                )
                if check_match:
                    active_check = check_match.group(0)

            link = SidebarLink(
                text=text, href=href, icon=icon, endpoint=endpoint, is_active_check=active_check
            )
            links.append(link)

        return links

    def to_dict(self) -> dict:
        """
        Convert parsed sidebar structure to dictionary.

        Returns:
            Dictionary representation of sidebar structure for JSON serialization.
        """
        return {
            "sections": [
                {
                    "title": section.title,
                    "feature_key": section.feature_key,
                    "submenus": [
                        {
                            "title": submenu.title,
                            "feature_key": submenu.feature_key,
                            "icon": submenu.icon,
                            "parent_section": submenu.parent_section,
                            "links": [
                                {
                                    "text": link.text,
                                    "href": link.href,
                                    "icon": link.icon,
                                    "endpoint": link.endpoint,
                                    "feature_key": link.feature_key,
                                }
                                for link in submenu.links
                            ],
                        }
                        for submenu in section.submenus
                    ],
                    "direct_links": [
                        {
                            "text": link.text,
                            "href": link.href,
                            "icon": link.icon,
                            "endpoint": link.endpoint,
                            "feature_key": link.feature_key,
                        }
                        for link in section.links
                    ],
                }
                for section in self.sections
            ]
        }

    def get_all_links(self) -> List[tuple]:
        """
        Get all links flattened with their hierarchy context.

        Returns:
            List of tuples: (section_title, submenu_title, link)
        """
        all_links = []

        for section in self.sections:
            # Direct section links
            for link in section.links:
                all_links.append((section.title, None, link))

            # Submenu links
            for submenu in section.submenus:
                for link in submenu.links:
                    all_links.append((section.title, submenu.title, link))

        return all_links

    def find_link_by_endpoint(self, endpoint: str) -> Optional[tuple]:
        """
        Find a link by its endpoint.

        Args:
            endpoint: Flask endpoint (e.g., 'strategic.capability_health')

        Returns:
            Tuple of (section_title, submenu_title, link) or None if not found.
        """
        for section_title, submenu_title, link in self.get_all_links():
            if link.endpoint == endpoint:
                return (section_title, submenu_title, link)

        return None


def parse_sidebar_template(template_path: Optional[str] = None) -> SidebarParser:
    """
    Convenience function to parse sidebar template.

    Args:
        template_path: Optional path to admin_sidebar.html

    Returns:
        SidebarParser instance with parsed sections.
    """
    parser = SidebarParser(template_path)
    parser.parse()
    return parser
