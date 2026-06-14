"""Feature State Manager

Automated detection and classification of feature states based on:
1. Presence of database queries (STUB vs PARTIAL)
2. Presence of working UI templates
3. Presence and pass rate of E2E tests
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class FeatureState(Enum):
    """Feature lifecycle states"""
    STUB = "STUB"
    PARTIAL = "PARTIAL"
    WORKING = "WORKING"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


@dataclass
class FeatureClassification:
    """Result of feature state classification"""
    route_file: str
    state: FeatureState
    has_db_queries: bool
    has_working_ui: bool
    has_e2e_tests: bool
    test_count: int
    confidence_score: float
    reasons: List[str]
    
    def to_dict(self) -> dict:
        return {
            "route_file": self.route_file,
            "state": self.state.value,
            "has_db_queries": self.has_db_queries,
            "has_working_ui": self.has_working_ui,
            "has_e2e_tests": self.has_e2e_tests,
            "test_count": self.test_count,
            "confidence_score": round(self.confidence_score, 2),
            "reasons": self.reasons
        }


class FeatureStateManager:
    """Detect and classify feature states"""
    
    # Patterns for detecting database queries
    DB_QUERY_PATTERNS = [
        r'db\.session\.query\(',
        r'db\.session\.add\(',
        r'db\.session\.delete\(',
        r'db\.session\.execute\(',
        r'\.filter\(',
        r'\.filter_by\(',
        r'\.all\(\)',
        r'\.first\(\)',
        r'\.get\(',
        r'\.order_by\(',
        r'\.limit\(',
        r'\.offset\(',
        r'\.join\(',
    ]
    
    # Patterns for detecting ORM models
    MODEL_PATTERNS = [
        r'from app\.models import',
        r'from app\.models\.',
        r'db\.Model',
    ]
    
    # Patterns for detecting templates
    TEMPLATE_PATTERNS = [
        r'render_template\(',
        r'render_template_string\(',
    ]
    
    def __init__(self, app_root: str = None):
        self.app_root = app_root or Path(__file__).parent.parent.parent
        self.routes_dir = Path(self.app_root) / "app" / "routes"
        self.templates_dir = Path(self.app_root) / "app" / "templates"
        self.tests_dir = Path(self.app_root) / "tests" / "e2e" / "journeys"
        self.feature_lifecycle_config = self._load_lifecycle_config()
    
    def _load_lifecycle_config(self) -> dict:
        """Load feature_lifecycle.yaml if it exists"""
        config_path = Path(self.app_root) / "feature_lifecycle.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def classify_all_features(self) -> List[FeatureClassification]:
        """Classify all features in app/routes/"""
        if not self.routes_dir.exists():
            return []
        
        classifications = []
        for route_file in sorted(self.routes_dir.glob("*_routes.py")):
            if route_file.name.startswith("__"):
                continue
            
            classification = self.classify_feature(route_file)
            classifications.append(classification)
        
        return classifications
    
    def classify_feature(self, route_file: Path) -> FeatureClassification:
        """Classify a single feature"""
        route_file = Path(route_file)
        
        # Read route file content
        try:
            with open(route_file, 'r') as f:
                content = f.read()
        except Exception as e:
            return FeatureClassification(
                route_file=route_file.name,
                state=FeatureState.STUB,
                has_db_queries=False,
                has_working_ui=False,
                has_e2e_tests=False,
                test_count=0,
                confidence_score=0.0,
                reasons=[f"Error reading file: {e}"]
            )
        
        # Check for database queries
        has_db_queries = self._has_db_queries(content)
        
        # Check for models
        has_models = self._has_models(content)
        
        # Check for templates
        has_templates = self._has_templates(content)
        
        # Check for working UI (templates that are not just error pages)
        has_working_ui = self._has_working_ui(route_file, content)
        
        # Check for E2E tests
        test_file, test_count = self._find_e2e_tests(route_file)
        has_e2e_tests = test_count > 0
        
        # Classify based on heuristics
        state, reasons, confidence = self._classify(
            has_db_queries=has_db_queries,
            has_models=has_models,
            has_templates=has_templates,
            has_working_ui=has_working_ui,
            has_e2e_tests=has_e2e_tests,
            route_file=route_file,
            content=content
        )
        
        return FeatureClassification(
            route_file=route_file.name,
            state=state,
            has_db_queries=has_db_queries,
            has_working_ui=has_working_ui,
            has_e2e_tests=has_e2e_tests,
            test_count=test_count,
            confidence_score=confidence,
            reasons=reasons
        )
    
    def _has_db_queries(self, content: str) -> bool:
        """Check if content has database queries"""
        for pattern in self.DB_QUERY_PATTERNS:
            if re.search(pattern, content):
                return True
        return False
    
    def _has_models(self, content: str) -> bool:
        """Check if content imports database models"""
        for pattern in self.MODEL_PATTERNS:
            if re.search(pattern, content):
                return True
        return False
    
    def _has_templates(self, content: str) -> bool:
        """Check if content renders templates"""
        for pattern in self.TEMPLATE_PATTERNS:
            if re.search(pattern, content):
                return True
        return False
    
    def _has_working_ui(self, route_file: Path, content: str) -> bool:
        """Check if templates exist and are not empty"""
        if not self._has_templates(content):
            return False
        
        # Extract template names from render_template calls
        pattern = r'render_template\([\'"]([^\'"]+)[\'"]'
        templates = re.findall(pattern, content)
        
        if not templates:
            return False
        
        # Check if any templates exist and have substantial content
        for template_name in templates:
            template_path = self.templates_dir / template_name
            if template_path.exists():
                try:
                    with open(template_path, 'r') as f:
                        template_content = f.read()
                    # Template is working if it has more than just HTML scaffold
                    if len(template_content.strip()) > 100:
                        return True
                except Exception as e:
                    logger.debug("Failed to read template %s: %s", template_path, e)

        return False
    
    def _find_e2e_tests(self, route_file: Path) -> Tuple[Optional[Path], int]:
        """Find E2E test file for this route and count tests"""
        if not self.tests_dir.exists():
            return None, 0
        
        # Extract feature name from route file (e.g., capability_map_routes.py -> capability_map)
        feature_name = route_file.stem.replace("_routes", "")
        
        # Look for matching test files
        for test_file in self.tests_dir.glob(f"test_*{feature_name}*.py"):
            try:
                with open(test_file, 'r') as f:
                    content = f.read()
                # Count test functions
                test_count = len(re.findall(r'def test_\w+\(', content))
                if test_count > 0:
                    return test_file, test_count
            except Exception as e:
                logger.debug("Failed to read test file %s: %s", test_file, e)
        
        return None, 0
    
    def _classify(
        self,
        has_db_queries: bool,
        has_models: bool,
        has_templates: bool,
        has_working_ui: bool,
        has_e2e_tests: bool,
        route_file: Path,
        content: str
    ) -> Tuple[FeatureState, List[str], float]:
        """Classify feature state based on heuristics"""
        reasons = []
        confidence = 0.0
        
        # Check for explicit deprecation markers
        if "DEPRECATED" in content or "deprecated" in content.lower():
            reasons.append("Found deprecation marker in route file")
            return FeatureState.DEPRECATED, reasons, 0.8
        
        # Decision tree
        if not has_db_queries and not has_models:
            reasons.append("No database queries or model imports found")
            confidence = 0.9
            
            # Check for placeholder patterns
            if "TODO" in content or "pass" in content or "NotImplemented" in content:
                reasons.append("Found placeholder code (TODO, pass, NotImplemented)")
                confidence = 0.95
            
            return FeatureState.STUB, reasons, confidence
        
        # Has models/queries but incomplete UI or no tests
        if has_db_queries and not has_e2e_tests:
            reasons.append("Has database queries but no E2E tests")
            confidence = 0.85
            return FeatureState.PARTIAL, reasons, confidence
        
        if has_db_queries and not has_working_ui:
            reasons.append("Has database queries but no working UI")
            confidence = 0.80
            return FeatureState.PARTIAL, reasons, confidence
        
        # Full implementation: DB queries + UI + E2E tests
        if has_db_queries and has_working_ui and has_e2e_tests:
            reasons.append("Complete: has DB queries, working UI, and E2E tests")
            confidence = 0.95
            return FeatureState.WORKING, reasons, confidence
        
        # Default to PARTIAL if we have some but not all
        if has_db_queries or has_models:
            reasons.append("Has models or queries but not fully tested/UI-complete")
            confidence = 0.70
            return FeatureState.PARTIAL, reasons, confidence
        
        # Fallback
        reasons.append("Could not determine state - defaulting to STUB")
        confidence = 0.5
        return FeatureState.STUB, reasons, confidence
    
    def get_summary(self, classifications: List[FeatureClassification]) -> dict:
        """Get summary statistics"""
        by_state = {}
        for state in FeatureState:
            by_state[state.value] = []
        
        for classification in classifications:
            by_state[classification.state.value].append(classification)
        
        return {
            "total": len(classifications),
            "by_state": {
                state: len(features) for state, features in by_state.items()
            },
            "stub_features": [c.route_file for c in by_state[FeatureState.STUB.value]],
            "partial_features": [c.route_file for c in by_state[FeatureState.PARTIAL.value]],
            "working_features": [c.route_file for c in by_state[FeatureState.WORKING.value]],
        }


def main():
    """CLI entry point"""
    import sys
    
    manager = FeatureStateManager()
    classifications = manager.classify_all_features()
    
    # Sort by state then by filename
    classifications.sort(
        key=lambda c: (
            list(FeatureState).index(c.state),
            c.route_file
        )
    )
    
    # Print results
    print("\n" + "="*80)
    print("FEATURE STATE CLASSIFICATION REPORT")
    print("="*80)
    
    for classification in classifications:
        print(f"\n{classification.route_file:50} {classification.state.value:10} (confidence: {classification.confidence_score:.0%})")
        for reason in classification.reasons:
            print(f"  • {reason}")
    
    # Summary
    summary = manager.get_summary(classifications)
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total features: {summary['total']}")
    for state, count in sorted(summary['by_state'].items()):
        print(f"  {state:15} {count:3} features")
    
    # JSON output
    json_output = {
        "total": summary['total'],
        "by_state": summary['by_state'],
        "classifications": [c.to_dict() for c in classifications]
    }
    
    output_file = Path("feature_state_report.json")
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2)
    
    print(f"\nJSON report written to: {output_file}")
    
    return 0 if summary['by_state'].get('STUB', 0) + summary['by_state'].get('PARTIAL', 0) == 0 else 1


if __name__ == "__main__":
    exit(main())
