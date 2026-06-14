"""
Data Integrity Checker

Provides comprehensive data integrity checks for import workflows.
"""

import logging
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import threading

from flask import current_app
from app import db

logger = logging.getLogger(__name__)

class IntegrityCheckType(Enum):
    """Types of integrity checks."""
    DUPLICATE_DETECTION = "duplicate_detection"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    BUSINESS_RULE_VALIDATION = "business_rule_validation"
    DATA_FORMAT_CONSISTENCY = "data_format_consistency"
    TEMPORAL_INTEGRITY = "temporal_integrity"
    COMPLETENESS_CHECK = "completeness_check"

class IntegrityStatus(Enum):
    """Integrity check status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

@dataclass
class IntegrityIssue:
    """Represents an integrity issue."""
    id: str
    check_type: IntegrityCheckType
    status: IntegrityStatus
    severity: str
    description: str
    affected_rows: List[int]
    affected_columns: List[str]
    details: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to dictionary."""
        return {
            'id': self.id,
            'check_type': self.check_type.value,
            'status': self.status.value,
            'severity': self.severity,
            'description': self.description,
            'affected_rows': self.affected_rows,
            'affected_columns': self.affected_columns,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class IntegrityCheckResult:
    """Represents the result of an integrity check."""
    check_type: IntegrityCheckType
    status: IntegrityStatus
    issues_found: List[IntegrityIssue]
    records_checked: int
    execution_time_ms: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'check_type': self.check_type.value,
            'status': self.status.value,
            'issues_found': [issue.to_dict() for issue in self.issues_found],
            'records_checked': self.records_checked,
            'execution_time_ms': self.execution_time_ms,
            'metadata': self.metadata
        }

class DataIntegrityChecker:
    """
    Checks data integrity for import workflows.
    """
    
    def __init__(self):
        """Initialize the data integrity checker."""
        self._check_rules = {}
        self._reference_data = {}
        self._business_rules = {}
        self._lock = threading.Lock()
        
        # Initialize default check rules
        self._initialize_check_rules()
        
        # Load reference data
        self._load_reference_data()
        
        # Load business rules
        self._load_business_rules()
    
    def _initialize_check_rules(self):
        """Initialize default integrity check rules."""
        self._check_rules = {
            'duplicate_detection': {
                'enabled': True,
                'sensitivity': 'medium',
                'fields': ['application_name', 'vendor_name', 'email'],
                'ignore_case': True,
                'ignore_whitespace': True
            },
            'referential_integrity': {
                'enabled': True,
                'sensitivity': 'high',
                'references': {
                    'business_unit': ['business_units'],
                    'department': ['departments'],
                    'category': ['categories']
                }
            },
            'business_rule_validation': {
                'enabled': True,
                'sensitivity': 'medium',
                'rules': {
                    'application_priority': ['high', 'medium', 'low'],
                    'vendor_rating': ['A', 'B', 'C', 'D'],
                    'user_role': ['admin', 'user', 'viewer']
                }
            },
            'data_format_consistency': {
                'enabled': True,
                'sensitivity': 'low',
                'formats': {
                    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                    'phone': r'^\+?[\d\s\-\(\)]{10,}$',
                    'url': r'^https?://[^\s/$.?#].[^\s]*$'
                }
            },
            'temporal_integrity': {
                'enabled': True,
                'sensitivity': 'medium',
                'date_fields': ['created_date', 'modified_date', 'last_login'],
                'future_date_threshold_days': 30,
                'past_date_threshold_years': 5
            },
            'completeness_check': {
                'enabled': True,
                'sensitivity': 'medium',
                'required_fields': {
                    'application_import': ['application_name', 'owner', 'business_unit'],
                    'vendor_import': ['vendor_name', 'contact_email', 'category'],
                    'user_import': ['username', 'email', 'first_name', 'last_name']
                }
            }
        }
    
    def _load_reference_data(self):
        """Load reference data for integrity checks."""
        try:
            # Load business units
            self._reference_data['business_units'] = self._get_business_units()
            
            # Load departments
            self._reference_data['departments'] = self._get_departments()
            
            # Load categories
            self._reference_data['categories'] = self._get_categories()
            
            # Load existing application names
            self._reference_data['application_names'] = self._get_application_names()
            
            # Load existing vendor names
            self._reference_data['vendor_names'] = self._get_vendor_names()
            
            # Load existing emails
            self._reference_data['emails'] = self._get_emails()
            
        except Exception as e:
            logger.warning(f"Failed to load reference data: {e}")
    
    def _load_business_rules(self):
        """Load business rules for validation."""
        try:
            # Load business rules from configuration
            self._business_rules = current_app.config.get('BUSINESS_INTEGRITY_RULES', {})
            
        except Exception as e:
            logger.warning(f"Failed to load business rules: {e}")
    
    def check_integrity(self, data: List[Dict[str, Any]], import_type: str, 
                       check_types: Optional[List[IntegrityCheckType]] = None) -> List[IntegrityCheckResult]:
        """
        Check data integrity for imported data.
        
        Args:
            data: List of data rows
            import_type: Type of import (application_import, vendor_import, etc.)
            check_types: Specific check types to run (None for all)
            
        Returns:
            List of integrity check results
        """
        results = []
        
        # Determine which checks to run
        if check_types is None:
            check_types = list(IntegrityCheckType)
        
        # Run each integrity check
        for check_type in check_types:
            if not self._check_rules.get(check_type.value, {}).get('enabled', True):
                continue
            
            start_time = datetime.utcnow()
            
            try:
                if check_type == IntegrityCheckType.DUPLICATE_DETECTION:
                    result = self._check_duplicates(data, import_type)
                elif check_type == IntegrityCheckType.REFERENTIAL_INTEGRITY:
                    result = self._check_referential_integrity(data, import_type)
                elif check_type == IntegrityCheckType.BUSINESS_RULE_VALIDATION:
                    result = self._check_business_rules(data, import_type)
                elif check_type == IntegrityCheckType.DATA_FORMAT_CONSISTENCY:
                    result = self._check_data_format_consistency(data, import_type)
                elif check_type == IntegrityCheckType.TEMPORAL_INTEGRITY:
                    result = self._check_temporal_integrity(data, import_type)
                elif check_type == IntegrityCheckType.COMPLETENESS_CHECK:
                    result = self._check_completeness(data, import_type)
                else:
                    result = IntegrityCheckResult(
                        check_type=check_type,
                        status=IntegrityStatus.SKIPPED,
                        issues_found=[],
                        records_checked=len(data),
                        execution_time_ms=0,
                        metadata={'reason': 'Unknown check type'}
                    )
                
                # Calculate execution time
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                result.execution_time_ms = int(execution_time)
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Integrity check {check_type.value} failed: {e}")
                results.append(IntegrityCheckResult(
                    check_type=check_type,
                    status=IntegrityStatus.FAILED,
                    issues_found=[],
                    records_checked=len(data),
                    execution_time_ms=0,
                    metadata={'error': str(e)}
                ))
        
        return results
    
    def _check_duplicates(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check for duplicate records."""
        issues = []
        rules = self._check_rules['duplicate_detection']
        
        # Get fields to check for duplicates
        fields = rules.get('fields', [])
        ignore_case = rules.get('ignore_case', True)
        ignore_whitespace = rules.get('ignore_whitespace', True)
        
        # Track seen values
        seen_values = {}
        
        for row_num, row in enumerate(data, 1):
            for field in fields:
                if field not in row:
                    continue
                
                value = str(row[field])
                
                # Apply normalization
                if ignore_case:
                    value = value.lower()
                if ignore_whitespace:
                    value = value.strip()
                
                # Create key for tracking
                key = f"{field}:{value}"
                
                if key in seen_values:
                    # Duplicate found
                    original_row = seen_values[key]
                    
                    issue = IntegrityIssue(
                        id=self._generate_issue_id(),
                        check_type=IntegrityCheckType.DUPLICATE_DETECTION,
                        status=IntegrityStatus.FAILED,
                        severity='medium',
                        description=f"Duplicate value found in {field}: '{row[field]}'",
                        affected_rows=[original_row, row_num],
                        affected_columns=[field],
                        details={
                            'duplicate_value': row[field],
                            'original_row': original_row,
                            'field': field
                        },
                        timestamp=datetime.utcnow()
                    )
                    issues.append(issue)
                else:
                    seen_values[key] = row_num
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.DUPLICATE_DETECTION,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'fields_checked': fields,
                'duplicates_found': len(issues)
            }
        )
    
    def _check_referential_integrity(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check referential integrity against reference data."""
        issues = []
        rules = self._check_rules['referential_integrity']
        references = rules.get('references', {})
        
        for row_num, row in enumerate(data, 1):
            for field, reference_tables in references.items():
                if field not in row:
                    continue
                
                value = row[field]
                
                # Check against each reference table
                for ref_table in reference_tables:
                    ref_data = self._reference_data.get(ref_table, [])
                    
                    if value not in ref_data:
                        issue = IntegrityIssue(
                            id=self._generate_issue_id(),
                            check_type=IntegrityCheckType.REFERENTIAL_INTEGRITY,
                            status=IntegrityStatus.FAILED,
                            severity='high',
                            description=f"Invalid reference in {field}: '{value}' not found in {ref_table}",
                            affected_rows=[row_num],
                            affected_columns=[field],
                            details={
                                'invalid_value': value,
                                'reference_table': ref_table,
                                'valid_values': ref_data[:10]  # Show first 10 valid values
                            },
                            timestamp=datetime.utcnow()
                        )
                        issues.append(issue)
                        break  # Only report once per field
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.REFERENTIAL_INTEGRITY,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'references_checked': references,
                'invalid_references': len(issues)
            }
        )
    
    def _check_business_rules(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check business rule compliance."""
        issues = []
        rules = self._check_rules['business_rule_validation']
        business_rules = rules.get('rules', {})
        
        # Add import type specific rules
        if import_type == 'application_import':
            business_rules.update({
                'status': ['active', 'inactive', 'pending'],
                'priority': ['high', 'medium', 'low']
            })
        elif import_type == 'vendor_import':
            business_rules.update({
                'category': ['software', 'hardware', 'services', 'consulting'],
                'rating': ['A', 'B', 'C', 'D']
            })
        elif import_type == 'user_import':
            business_rules.update({
                'role': ['admin', 'user', 'viewer'],
                'active': ['true', 'false', '1', '0']
            })
        
        for row_num, row in enumerate(data, 1):
            for field, allowed_values in business_rules.items():
                if field not in row:
                    continue
                
                value = str(row[field]).lower()
                
                if value not in [av.lower() for av in allowed_values]:
                    issue = IntegrityIssue(
                        id=self._generate_issue_id(),
                        check_type=IntegrityCheckType.BUSINESS_RULE_VALIDATION,
                        status=IntegrityStatus.FAILED,
                        severity='medium',
                        description=f"Invalid business rule value in {field}: '{row[field]}' not in allowed values",
                        affected_rows=[row_num],
                        affected_columns=[field],
                        details={
                            'invalid_value': row[field],
                            'field': field,
                            'allowed_values': allowed_values
                        },
                        timestamp=datetime.utcnow()
                    )
                    issues.append(issue)
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.BUSINESS_RULE_VALIDATION,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'business_rules_checked': business_rules,
                'rule_violations': len(issues)
            }
        )
    
    def _check_data_format_consistency(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check data format consistency."""
        issues = []
        rules = self._check_rules['data_format_consistency']
        formats = rules.get('formats', {})
        
        for row_num, row in enumerate(data, 1):
            for field, pattern in formats.items():
                if field not in row:
                    continue
                
                value = str(row[field])
                
                if not re.match(pattern, value):
                    issue = IntegrityIssue(
                        id=self._generate_issue_id(),
                        check_type=IntegrityCheckType.DATA_FORMAT_CONSISTENCY,
                        status=IntegrityStatus.WARNING,
                        severity='low',
                        description=f"Inconsistent format in {field}: '{value}' does not match expected pattern",
                        affected_rows=[row_num],
                        affected_columns=[field],
                        details={
                            'invalid_value': value,
                            'field': field,
                            'expected_pattern': pattern
                        },
                        timestamp=datetime.utcnow()
                    )
                    issues.append(issue)
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.DATA_FORMAT_CONSISTENCY,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'formats_checked': formats,
                'format_violations': len(issues)
            }
        )
    
    def _check_temporal_integrity(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check temporal integrity of dates."""
        issues = []
        rules = self._check_rules['temporal_integrity']
        date_fields = rules.get('date_fields', [])
        future_threshold = timedelta(days=rules.get('future_date_threshold_days', 30))
        past_threshold = timedelta(days=rules.get('past_date_threshold_years', 5) * 365)
        
        now = datetime.utcnow()
        
        for row_num, row in enumerate(data, 1):
            for field in date_fields:
                if field not in row:
                    continue
                
                value = str(row[field])
                
                # Try to parse date
                parsed_date = None
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                
                if parsed_date:
                    # Check for future dates
                    if parsed_date > now + future_threshold:
                        issue = IntegrityIssue(
                            id=self._generate_issue_id(),
                            check_type=IntegrityCheckType.TEMPORAL_INTEGRITY,
                            status=IntegrityStatus.WARNING,
                            severity='low',
                            description=f"Future date detected in {field}: '{value}'",
                            affected_rows=[row_num],
                            affected_columns=[field],
                            details={
                                'date_value': value,
                                'field': field,
                                'days_in_future': (parsed_date - now).days
                            },
                            timestamp=datetime.utcnow()
                        )
                        issues.append(issue)
                    
                    # Check for very old dates
                    elif parsed_date < now - past_threshold:
                        issue = IntegrityIssue(
                            id=self._generate_issue_id(),
                            check_type=IntegrityCheckType.TEMPORAL_INTEGRITY,
                            status=IntegrityStatus.WARNING,
                            severity='low',
                            description=f"Very old date detected in {field}: '{value}'",
                            affected_rows=[row_num],
                            affected_columns=[field],
                            details={
                                'date_value': value,
                                'field': field,
                                'years_ago': (now - parsed_date).days / 365
                            },
                            timestamp=datetime.utcnow()
                        )
                        issues.append(issue)
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.TEMPORAL_INTEGRITY,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'date_fields_checked': date_fields,
                'temporal_issues': len(issues)
            }
        )
    
    def _check_completeness(self, data: List[Dict[str, Any]], import_type: str) -> IntegrityCheckResult:
        """Check data completeness."""
        issues = []
        rules = self._check_rules['completeness_check']
        required_fields = rules.get('required_fields', {}).get(import_type, [])
        
        for row_num, row in enumerate(data, 1):
            for field in required_fields:
                if field not in row or not row[field] or str(row[field]).strip() == '':
                    issue = IntegrityIssue(
                        id=self._generate_issue_id(),
                        check_type=IntegrityCheckType.COMPLETENESS_CHECK,
                        status=IntegrityStatus.FAILED,
                        severity='medium',
                        description=f"Missing or empty required field: {field}",
                        affected_rows=[row_num],
                        affected_columns=[field],
                        details={
                            'field': field,
                            'value': row.get(field, ''),
                            'import_type': import_type
                        },
                        timestamp=datetime.utcnow()
                    )
                    issues.append(issue)
        
        status = IntegrityStatus.FAILED if issues else IntegrityStatus.PASSED
        
        return IntegrityCheckResult(
            check_type=IntegrityCheckType.COMPLETENESS_CHECK,
            status=status,
            issues_found=issues,
            records_checked=len(data),
            execution_time_ms=0,
            metadata={
                'required_fields': required_fields,
                'completeness_issues': len(issues)
            }
        )
    
    def _get_business_units(self) -> List[str]:
        """Get list of business units."""
        try:
            # Query database for business units
            from app.models import BusinessUnit
            units = BusinessUnit.query.with_entities(BusinessUnit.name).all()
            return [unit.name for unit in units]
        except Exception as e:
            logger.warning(f"Failed to get business units: {e}")
            return []
    
    def _get_departments(self) -> List[str]:
        """Get list of departments."""
        try:
            # Query database for departments
            from app.models import Department
            departments = Department.query.with_entities(Department.name).all()
            return [dept.name for dept in departments]
        except Exception as e:
            logger.warning(f"Failed to get departments: {e}")
            return []
    
    def _get_categories(self) -> List[str]:
        """Get list of categories."""
        try:
            # Query database for categories
            from app.models import Category
            categories = Category.query.with_entities(Category.name).all()
            return [cat.name for cat in categories]
        except Exception as e:
            logger.warning(f"Failed to get categories: {e}")
            return []
    
    def _get_application_names(self) -> Set[str]:
        """Get set of existing application names."""
        try:
            from app.models import ApplicationComponent
            apps = ApplicationComponent.query.with_entities(ApplicationComponent.name).all()
            return set(app.name for app in apps)
        except Exception as e:
            logger.warning(f"Failed to get application names: {e}")
            return set()
    
    def _get_vendor_names(self) -> Set[str]:
        """Get set of existing vendor names."""
        try:
            from app.models import VendorOrganization
            vendors = VendorOrganization.query.with_entities(VendorOrganization.name).all()
            return set(vendor.name for vendor in vendors)
        except Exception as e:
            logger.warning(f"Failed to get vendor names: {e}")
            return set()
    
    def _get_emails(self) -> Set[str]:
        """Get set of existing emails."""
        try:
            from app.models import User
            users = User.query.with_entities(User.email).all()
            return set(user.email for user in users)
        except Exception as e:
            logger.warning(f"Failed to get emails: {e}")
            return set()
    
    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"issue_{timestamp}_{threading.get_ident()}"
        return data
    
    def get_integrity_summary(self, results: List[IntegrityCheckResult]) -> Dict[str, Any]:
        """
        Get summary of integrity check results.
        
        Args:
            results: List of integrity check results
            
        Returns:
            Integrity summary
        """
        total_checks = len(results)
        passed_checks = len([r for r in results if r.status == IntegrityStatus.PASSED])
        failed_checks = len([r for r in results if r.status == IntegrityStatus.FAILED])
        warning_checks = len([r for r in results if r.status == IntegrityStatus.WARNING])
        
        total_issues = sum(len(r.issues_found) for r in results)
        
        # Group issues by type
        issue_types = {}
        for result in results:
            check_type = result.check_type.value
            issue_types[check_type] = issue_types.get(check_type, 0) + len(result.issues_found)
        
        # Group issues by severity
        severity_counts = {}
        for result in results:
            for issue in result.issues_found:
                severity = issue.severity
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': failed_checks,
            'warning_checks': warning_checks,
            'success_rate': passed_checks / total_checks if total_checks > 0 else 0,
            'total_issues': total_issues,
            'issue_types': issue_types,
            'severity_distribution': severity_counts,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def update_reference_data(self, reference_type: str, data: List[str]):
        """Update reference data for integrity checks."""
        with self._lock:
            self._reference_data[reference_type] = data
        logger.info(f"Updated reference data for {reference_type}: {len(data)} items")
    
    def add_business_rule(self, field: str, allowed_values: List[str]):
        """Add a business rule."""
        with self._lock:
            if 'business_rule_validation' not in self._check_rules:
                self._check_rules['business_rule_validation'] = {'rules': {}}
            
            self._check_rules['business_rule_validation']['rules'][field] = allowed_values
        logger.info(f"Added business rule for {field}: {allowed_values}")

# Global data integrity checker instance
data_integrity_checker = DataIntegrityChecker()
