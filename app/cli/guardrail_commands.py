"""
Guardrail CLI Commands
Flask CLI commands for guardrail validation and enforcement
"""
import glob
import os
import re
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def validate_guardrails():
    """Validate all guardrails and report violations"""
    print("🔍 Running comprehensive guardrail validation...")

    violations = []

    # UI Fragmentation Check
    print("\n📋 Checking UI fragmentation...")
    ui_violations = check_ui_fragmentation()
    violations.extend(ui_violations)

    # API Consistency Check
    print("🔌 Checking API consistency...")
    api_violations = check_api_consistency()
    violations.extend(api_violations)

    # Pattern Reuse Check
    print("🔄 Checking pattern reuse...")
    pattern_violations = check_pattern_reuse()
    violations.extend(pattern_violations)

    # Report results
    if violations:
        print(f"\n🚨 GUARDRAIL VIOLATIONS DETECTED: {len(violations)}")
        for i, violation in enumerate(violations, 1):
            print(f"  {i}. {violation}")

        return False
    else:
        print("\n✅ All guardrails compliant!")
        return True


def check_ui_fragmentation():
    """Check for UI table fragmentation"""
    violations = []
    template_dir = Path("app/templates")

    if not template_dir.exists():
        return ["TEMPLATE_DIR_NOT_FOUND: app/templates directory not found"]

    # Find all HTML files
    html_files = list(template_dir.rglob("*.html"))

    entity_tables = {}

    for file_path in html_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract table information
            tables = extract_tables_from_content(content)

            for table in tables:
                entity_type = identify_entity_type(content, file_path)

                if entity_type:
                    if entity_type not in entity_tables:
                        entity_tables[entity_type] = []

                    entity_tables[entity_type].append(
                        {
                            "file": str(file_path.relative_to(template_dir)),
                            "headers": table["headers"],
                            "hash": hash_headers(table["headers"]),
                        }
                    )

        except Exception as e:
            violations.append(f"FILE_ERROR: {file_path.name} - {str(e)}")

    # Check for fragmentation
    for entity_type, tables in entity_tables.items():
        unique_hashes = set(t["hash"] for t in tables)

        if len(unique_hashes) > 1:
            violations.append(
                f"UI_FRAGMENTATION: {entity_type} has {len(unique_hashes)} different table structures"
            )

            # Group by structure
            structure_groups = {}
            for table in tables:
                if table["hash"] not in structure_groups:
                    structure_groups[table["hash"]] = []
                structure_groups[table["hash"]].append(table)

            for hash_val, group in structure_groups.items():
                violations.append(f"  Structure {hash_val[:8]}: {len(group)} files")
                for table in group:
                    violations.append(f"    - {table['file']}: {table['headers']}")

    return violations


def check_api_consistency():
    """Check for API endpoint consistency"""
    violations = []

    # Find all route files
    route_files = list(Path("app").rglob("routes*.py"))
    route_files.extend(Path("app").rglob("*_routes.py"))

    if not route_files:
        return ["NO_ROUTE_FILES_FOUND: No route files found"]

    api_endpoints = {}

    for file_path in route_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract API routes
            routes = extract_api_routes(content)

            for route in routes:
                key = f"{route['method']}:{route['path']}"

                if key not in api_endpoints:
                    api_endpoints[key] = []

                api_endpoints[key].append(
                    {"file": str(file_path.relative_to(Path("app"))), "function": route["function"]}
                )

        except Exception as e:
            violations.append(f"FILE_ERROR: {file_path.name} - {str(e)}")

    # Check for duplicates
    for endpoint_key, definitions in api_endpoints.items():
        if len(definitions) > 1:
            violations.append(f"API_DUPLICATE: {endpoint_key} defined {len(definitions)} times")
            for definition in definitions:
                violations.append(f"  - {definition['file']}: {definition['function']}")

    return violations


def check_pattern_reuse():
    """Check for pattern reuse violations"""
    violations = []

    # Check for duplicated component patterns
    template_dir = Path("app/templates")

    if not template_dir.exists():
        return ["TEMPLATE_DIR_NOT_FOUND: app/templates directory not found"]

    component_patterns = {}

    for file_path in template_dir.rglob("*.html"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract component patterns
            components = extract_component_patterns(content)

            for component in components:
                pattern_hash = hash_component_pattern(component)

                if pattern_hash not in component_patterns:
                    component_patterns[pattern_hash] = []

                component_patterns[pattern_hash].append(
                    {
                        "file": str(file_path.relative_to(template_dir)),
                        "component": component["name"],
                        "size": len(component["content"]),
                    }
                )

        except Exception as e:
            violations.append(f"FILE_ERROR: {file_path.name} - {str(e)}")

    # Check for duplicate patterns
    for pattern_hash, components in component_patterns.items():
        if len(components) > 1:
            # Only flag if components are similar in size (likely duplicates)
            sizes = [c["size"] for c in components]
            if max(sizes) - min(sizes) < 50:  # Within 50 characters
                violations.append(f"PATTERN_DUPLICATE: {len(components)} similar components")
                for component in components:
                    violations.append(
                        f"  - {component['file']}: {component['component']} ({component['size']} chars)"
                    )

    return violations


def extract_tables_from_content(content):
    """Extract table information from HTML content"""
    tables = []

    # Find table headers
    table_pattern = r"<table[^>]*>.*?<thead[^>]*>.*?<tr[^>]*>(.*?)</tr>.*?</thead>.*?</table>"
    table_matches = re.findall(table_pattern, content, re.DOTALL | re.IGNORECASE)

    for match in table_matches:
        # Extract headers
        header_pattern = r"<th[^>]*>(.*?)</th>"
        headers = re.findall(header_pattern, match, re.IGNORECASE)

        # Clean headers
        clean_headers = []
        for header in headers:
            clean = re.sub(r"<[^>]+>", "", header).strip()
            if clean:
                clean_headers.append(clean)

        if clean_headers:
            tables.append({"headers": clean_headers})

    return tables


def extract_api_routes(content):
    """Extract API route information from Python content"""
    routes = []

    # Find route decorators
    route_pattern = (
        r'@([^.]+)\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?.*?def\s+(\w+)\('
    )
    matches = re.findall(route_pattern, content, re.MULTILINE | re.DOTALL)

    for blueprint, path, methods, function in matches:
        method_list = ["GET"]  # Default
        if methods:
            method_list = [m.strip().strip("'\"") for m in methods.split(",")]

        for method in method_list:
            if method.upper() in ["GET", "POST", "PUT", "DELETE"]:
                routes.append(
                    {
                        "blueprint": blueprint,
                        "path": path,
                        "method": method.upper(),
                        "function": function,
                    }
                )

    return routes


def extract_component_patterns(content):
    """Extract component patterns from HTML content"""
    components = []

    # Find component definitions (Alpine.js, Vue-like, etc.)
    component_patterns = [
        r"x-data\s*=\s*{([^}]+)}",  # Alpine.js
        r"<div[^>]*x-data[^>]*>.*?</div>",  # Alpine.js divs
        r'class="[^"]*component[^"]*"',  # Component classes
    ]

    for pattern in component_patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        for i, match in enumerate(matches):
            components.append(
                {
                    "name": f"component_{i}",
                    "content": match[:200],  # First 200 chars for pattern matching
                }
            )

    return components


def identify_entity_type(content, file_path):
    """Identify entity type from content and file path"""
    file_path_str = str(file_path).lower()
    content_lower = content.lower()

    # Check file path
    if "manufacturing" in file_path_str:
        return "manufacturing_capability"
    elif "unified" in file_path_str:
        return "unified_capability"
    elif "capability" in file_path_str:
        return "application_capability"

    # Check content
    if "manufacturing capability" in content_lower:
        return "manufacturing_capability"
    elif "unified capability" in content_lower:
        return "unified_capability"
    elif "application capability" in content_lower:
        return "application_capability"

    return None


def hash_headers(headers):
    """Create hash from headers for comparison"""
    normalized = [h.lower().replace(" ", "_").replace("-", "_") for h in headers]
    return hash(tuple(sorted(normalized)))


def hash_component_pattern(content):
    """Create hash from component content"""
    # Normalize content for comparison
    normalized = re.sub(r"\s+", " ", content.lower().strip())
    return hash(normalized[:100])  # First 100 chars


def fix_fragmentation():
    """Attempt to auto-fix detected fragmentation"""
    print("🔧 Attempting to auto-fix fragmentation...")

    # This would implement auto-fixing logic
    # For now, just report what would be fixed
    print("⚠️  Auto-fix not implemented yet")
    print("📝 Manual fixes required:")
    print("  1. Standardize table headers across all capability views")
    print("  2. Use consistent column ordering")
    print("  3. Apply unified styling patterns")

    return True


# CLI Commands
@click.command()
@click.option("--fix", is_flag=True, help="Attempt to auto-fix violations")
def guardrails(fix):
    """Validate guardrails and optionally fix violations"""
    if fix:
        fix_fragmentation()
    else:
        success = validate_guardrails()
        sys.exit(0 if success else 1)


@click.command()
def guardrail_stats():
    """Show guardrail statistics"""
    print("📊 Guardrail Statistics:")

    # Count files
    template_files = len(list(Path("app/templates").rglob("*.html")))
    route_files = len(list(Path("app").rglob("routes*.py")))

    print(f"  Template files: {template_files}")
    print(f"  Route files: {route_files}")

    # Check for potential issues
    violations = validate_guardrails()
    print(f"  Violations: {len(violations) if violations else 0}")


@click.command()
def check_ui():
    """Check UI fragmentation specifically"""
    violations = check_ui_fragmentation()

    if violations:
        print(f"🚨 UI Fragmentation Issues: {len(violations)}")
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ No UI fragmentation detected")
        sys.exit(0)


@click.command()
def check_api():
    """Check API consistency specifically"""
    violations = check_api_consistency()

    if violations:
        print(f"🚨 API Consistency Issues: {len(violations)}")
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ No API consistency issues detected")
        sys.exit(0)
