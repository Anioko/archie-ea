"""
Workflow State Validator

Provides comprehensive state validation for workflow executions.
"""

import logging
import re
from datetime import datetime, timedelta  # dead-code-ok
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import threading

from flask import current_app
from app import db  # dead-code-ok

logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ValidationStatus(Enum):
    """Validation status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ValidationRule:
    """Represents a validation rule."""
    id: str
    name: str
    description: str
    severity: ValidationSeverity
    enabled: bool
    validator: Callable
    conditions: Dict[str, Any]
    metadata: Dict[str, Any]

@dataclass
class ValidationResult:
    """Represents a validation result."""
    rule_id: str
    workflow_id: str
    step_id: Optional[str]
    status: ValidationStatus
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    execution_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            'rule_id': self.rule_id,
            'workflow_id': self.workflow_id,
            'step_id': self.step_id,
            'status': self.status.value,
            'severity': self.severity.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'execution_time': self.execution_time
        }

class WorkflowStateValidator:
    """
    Validates workflow state and ensures data integrity.
    """
    
    def __init__(self):
        """Initialize the workflow state validator."""
        self._rules = {}  # rule_id -> ValidationRule
        self._validation_history = {}  # workflow_id -> [ValidationResult]
        self._lock = threading.Lock()
        
        # Initialize default validation rules
        self._initialize_default_rules()
        
        # Load custom rules from configuration
        self._load_custom_rules()
    
    def _initialize_default_rules(self):
        """Initialize default validation rules."""
        self._rules = {
            'workflow_state_integrity': ValidationRule(
                id='workflow_state_integrity',
                name='Workflow State Integrity',
                description='Validates workflow state data integrity',
                severity=ValidationSeverity.CRITICAL,
                enabled=True,
                validator=self._validate_state_integrity,
                conditions={},
                metadata={'category': 'integrity'}
            ),
            'required_fields_present': ValidationRule(
                id='required_fields_present',
                name='Required Fields Present',
                description='Ensures all required fields are present in workflow state',
                severity=ValidationSeverity.ERROR,
                enabled=True,
                validator=self._validate_required_fields,
                conditions={},
                metadata={'category': 'completeness'}
            ),
            'data_type_consistency': ValidationRule(
                id='data_type_consistency',
                name='Data Type Consistency',
                description='Validates data type consistency across workflow state',
                severity=ValidationSeverity.WARNING,
                enabled=True,
                validator=self._validate_data_types,
                conditions={},
                metadata={'category': 'consistency'}
            ),
            'business_rule_compliance': ValidationRule(
                id='business_rule_compliance',
                name='Business Rule Compliance',
                description='Validates compliance with business rules',
                severity=ValidationSeverity.ERROR,
                enabled=True,
                validator=self._validate_business_rules,
                conditions={},
                metadata={'category': 'business'}
            ),
            'resource_availability': ValidationRule(
                id='resource_availability',
                name='Resource Availability',
                description='Validates availability of required resources',
                severity=ValidationSeverity.WARNING,
                enabled=True,
                validator=self._validate_resource_availability,
                conditions={},
                metadata={'category': 'resources'}
            ),
            'security_constraints': ValidationRule(
                id='security_constraints',
                name='Security Constraints',
                description='Validates security constraints and permissions',
                severity=ValidationSeverity.CRITICAL,
                enabled=True,
                validator=self._validate_security_constraints,
                conditions={},
                metadata={'category': 'security'}
            ),
            'temporal_consistency': ValidationRule(
                id='temporal_consistency',
                name='Temporal Consistency',
                description='Validates temporal consistency of workflow data',
                severity=ValidationSeverity.WARNING,
                enabled=True,
                validator=self._validate_temporal_consistency,
                conditions={},
                metadata={'category': 'temporal'}
            ),
            'reference_integrity': ValidationRule(
                id='reference_integrity',
                name='Reference Integrity',
                description='Validates integrity of references and relationships',
                severity=ValidationSeverity.ERROR,
                enabled=True,
                validator=self._validate_reference_integrity,
                conditions={},
                metadata={'category': 'integrity'}
            ),
            'performance_thresholds': ValidationRule(
                id='performance_thresholds',
                name='Performance Thresholds',
                description='Validates performance thresholds are not exceeded',
                severity=ValidationSeverity.INFO,
                enabled=True,
                validator=self._validate_performance_thresholds,
                conditions={},
                metadata={'category': 'performance'}
            ),
            'data_quality_metrics': ValidationRule(
                id='data_quality_metrics',
                name='Data Quality Metrics',
                description='Validates data quality metrics and standards',
                severity=ValidationSeverity.WARNING,
                enabled=True,
                validator=self._validate_data_quality,
                conditions={},
                metadata={'category': 'quality'}
            )
        }
    
    def _load_custom_rules(self):
        """Load custom validation rules from configuration."""
        try:
            # Load from app configuration
            custom_rules = current_app.config.get('WORKFLOW_VALIDATION_RULES', {})
            
            for rule_id, config in custom_rules.items():
                # Create custom validator function
                validator_code = config.get('validator')
                if validator_code:
                    # In a real implementation, this would safely evaluate the validator code
                    # For now, skip custom validators for security
                    continue
                
                severity = ValidationSeverity(config.get('severity', 'warning'))
                
                self._rules[rule_id] = ValidationRule(
                    id=rule_id,
                    name=config.get('name', rule_id),
                    description=config.get('description', ''),
                    severity=severity,
                    enabled=config.get('enabled', True),
                    validator=self._default_validator,  # Placeholder
                    conditions=config.get('conditions', {}),
                    metadata=config.get('metadata', {})
                )
                
        except Exception as e:
            logger.warning(f"Failed to load custom validation rules: {e}")
    
    def validate_workflow_state(self, workflow_id: str, state_data: Dict[str, Any],
                               step_id: Optional[str] = None, 
                               rule_ids: Optional[List[str]] = None) -> List[ValidationResult]:
        """
        Validate workflow state against configured rules.
        
        Args:
            workflow_id: Workflow instance ID
            state_data: Current workflow state
            step_id: Optional step ID
            rule_ids: Optional list of specific rules to validate
            
        Returns:
            List of validation results
        """
        results = []
        
        # Determine which rules to run
        if rule_ids:
            rules_to_run = [self._rules[rid] for rid in rule_ids if rid in self._rules]
        else:
            rules_to_run = [rule for rule in self._rules.values() if rule.enabled]
        
        # Run each validation rule
        for rule in rules_to_run:
            try:
                start_time = datetime.utcnow()
                
                # Check rule conditions
                if not self._check_rule_conditions(rule, state_data):
                    continue
                
                # Run validation
                status, message, details = rule.validator(workflow_id, state_data, step_id)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Create validation result
                result = ValidationResult(
                    rule_id=rule.id,
                    workflow_id=workflow_id,
                    step_id=step_id,
                    status=status,
                    severity=rule.severity,
                    message=message,
                    details=details,
                    timestamp=datetime.utcnow(),
                    execution_time=execution_time
                )
                
                results.append(result)
                
                # Store in history
                with self._lock:
                    if workflow_id not in self._validation_history:
                        self._validation_history[workflow_id] = []
                    self._validation_history[workflow_id].append(result)
                
                # Log validation result
                log_level = {
                    ValidationSeverity.INFO: logger.info,
                    ValidationSeverity.WARNING: logger.warning,
                    ValidationSeverity.ERROR: logger.error,
                    ValidationSeverity.CRITICAL: logger.critical
                }.get(rule.severity, logger.info)
                
                log_level(f"Validation {status.value}: {rule.name} - {message}")
                
            except Exception as e:
                logger.error(f"Validation rule {rule.id} failed: {e}")
                
                # Create error result
                error_result = ValidationResult(
                    rule_id=rule.id,
                    workflow_id=workflow_id,
                    step_id=step_id,
                    status=ValidationStatus.FAILED,
                    severity=ValidationSeverity.ERROR,
                    message=f"Validation rule failed: {str(e)}",
                    details={'error': str(e)},
                    timestamp=datetime.utcnow(),
                    execution_time=0.0
                )
                
                results.append(error_result)
        
        return results
    
    def _check_rule_conditions(self, rule: ValidationRule, state_data: Dict[str, Any]) -> bool:
        """Check if rule conditions are met."""
        conditions = rule.conditions
        
        # Check workflow type condition
        if 'workflow_type' in conditions:
            workflow_type = state_data.get('workflow_type')
            if workflow_type != conditions['workflow_type']:
                return False
        
        # Check step condition
        if 'step_id' in conditions:
            step_id = state_data.get('current_step')
            if step_id != conditions['step_id']:
                return False
        
        # Check data presence condition
        if 'requires_data' in conditions:
            required_data = conditions['requires_data']
            for data_field in required_data:
                if data_field not in state_data:
                    return False
        
        return True
    
    def _validate_state_integrity(self, workflow_id: str, state_data: Dict[str, Any], 
                                step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate workflow state integrity."""
        try:
            # Check for corrupted data
            if not isinstance(state_data, dict):
                return ValidationStatus.FAILED, "State data is not a dictionary", {}
            
            # Check for required top-level fields
            required_fields = ['workflow_id', 'status', 'created_at']
            missing_fields = [field for field in required_fields if field not in state_data]
            
            if missing_fields:
                return ValidationStatus.FAILED, f"Missing required fields: {', '.join(missing_fields)}", {'missing_fields': missing_fields}
            
            # Check data consistency
            workflow_id_in_state = state_data.get('workflow_id')
            if workflow_id_in_state != workflow_id:
                return ValidationStatus.FAILED, "Workflow ID mismatch", {
                    'expected': workflow_id,
                    'actual': workflow_id_in_state
                }
            
            # Check for circular references
            if self._has_circular_references(state_data):
                return ValidationStatus.FAILED, "Circular references detected in state data", {}
            
            return ValidationStatus.PASSED, "State integrity validated", {'fields_checked': len(state_data)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"State integrity validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_required_fields(self, workflow_id: str, state_data: Dict[str, Any],
                                 step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate required fields are present."""
        try:
            # Define required fields based on workflow type
            workflow_type = state_data.get('workflow_type', 'unknown')
            
            required_fields_map = {
                'application_onboarding': ['application_name', 'owner', 'business_unit'],
                'gap_analysis': ['current_state', 'desired_state', 'gap_criteria'],
                'vendor_selection': ['requirements', 'evaluation_criteria', 'vendors'],
                'consolidation': ['applications', 'consolidation_criteria']
            }
            
            required_fields = required_fields_map.get(workflow_type, [])
            
            # Check required fields
            missing_fields = [field for field in required_fields if field not in state_data or state_data[field] is None]
            
            if missing_fields:
                return ValidationStatus.FAILED, f"Missing required fields: {', '.join(missing_fields)}", {
                    'missing_fields': missing_fields,
                    'workflow_type': workflow_type
                }
            
            return ValidationStatus.PASSED, "All required fields present", {'fields_checked': len(required_fields)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Required fields validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_data_types(self, workflow_id: str, state_data: Dict[str, Any],
                            step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate data type consistency."""
        try:
            type_errors = []
            
            # Define expected types for common fields
            expected_types = {
                'workflow_id': str,
                'created_at': (str, datetime),
                'updated_at': (str, datetime),
                'status': str,
                'priority': (str, int),
                'progress': (int, float)
            }
            
            # Check data types
            for field, expected_type in expected_types.items():
                if field in state_data:
                    value = state_data[field]
                    if not isinstance(value, expected_type):
                        type_errors.append(f"{field}: expected {expected_type}, got {type(value)}")
            
            if type_errors:
                return ValidationStatus.FAILED, f"Data type inconsistencies: {', '.join(type_errors)}", {
                    'type_errors': type_errors
                }
            
            return ValidationStatus.PASSED, "Data types are consistent", {'fields_checked': len(expected_types)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Data type validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_business_rules(self, workflow_id: str, state_data: Dict[str, Any],
                                step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate business rule compliance."""
        try:
            business_violations = []
            
            # Check business rules based on workflow type
            workflow_type = state_data.get('workflow_type', 'unknown')
            
            if workflow_type == 'application_onboarding':
                # Application onboarding rules
                if 'application_name' in state_data:
                    app_name = state_data['application_name']
                    if len(app_name) < 3:
                        business_violations.append("Application name must be at least 3 characters")
                
                if 'owner' in state_data:
                    owner = state_data['owner']
                    if not owner or not isinstance(owner, str):
                        business_violations.append("Application owner is required")
            
            elif workflow_type == 'vendor_selection':
                # Vendor selection rules
                vendors = state_data.get('vendors', [])
                if len(vendors) < 2:
                    business_violations.append("At least 2 vendors required for selection")
                
                evaluation_criteria = state_data.get('evaluation_criteria', {})
                if len(evaluation_criteria) < 3:
                    business_violations.append("At least 3 evaluation criteria required")
            
            elif workflow_type == 'consolidation':
                # Consolidation rules
                applications = state_data.get('applications', [])
                if len(applications) < 2:
                    business_violations.append("At least 2 applications required for consolidation")
            
            if business_violations:
                return ValidationStatus.FAILED, f"Business rule violations: {', '.join(business_violations)}", {
                    'violations': business_violations,
                    'workflow_type': workflow_type
                }
            
            return ValidationStatus.PASSED, "Business rules validated", {'workflow_type': workflow_type}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Business rule validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_resource_availability(self, workflow_id: str, state_data: Dict[str, Any],
                                      step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate resource availability."""
        try:
            resource_issues = []
            
            # Check for required resources
            required_resources = state_data.get('required_resources', [])
            
            for resource in required_resources:
                resource_name = resource.get('name')
                resource_type = resource.get('type')
                
                # Simulate resource availability check
                if not self._is_resource_available(resource_name, resource_type):
                    resource_issues.append(f"Resource {resource_name} ({resource_type}) is not available")
            
            if resource_issues:
                return ValidationStatus.FAILED, f"Resource availability issues: {', '.join(resource_issues)}", {
                    'unavailable_resources': resource_issues
                }
            
            return ValidationStatus.PASSED, "All required resources are available", {'resources_checked': len(required_resources)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Resource availability validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_security_constraints(self, workflow_id: str, state_data: Dict[str, Any],
                                     step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate security constraints."""
        try:
            security_violations = []
            
            # Check for sensitive data exposure
            sensitive_patterns = [
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card numbers
                r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Email addresses
            ]
            
            for key, value in state_data.items():
                if isinstance(value, str):
                    for pattern in sensitive_patterns:
                        if re.search(pattern, value):
                            security_violations.append(f"Sensitive data detected in field: {key}")
            
            # Check permission constraints
            user_id = state_data.get('user_id')
            required_permissions = state_data.get('required_permissions', [])
            
            if user_id and required_permissions:
                if not self._user_has_permissions(user_id, required_permissions):
                    security_violations.append(f"User {user_id} lacks required permissions")
            
            if security_violations:
                return ValidationStatus.FAILED, f"Security violations: {', '.join(security_violations)}", {
                    'violations': security_violations
                }
            
            return ValidationStatus.PASSED, "Security constraints validated", {'permissions_checked': len(required_permissions)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Security constraint validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_temporal_consistency(self, workflow_id: str, state_data: Dict[str, Any],
                                    step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate temporal consistency."""
        try:
            temporal_issues = []
            
            # Check date consistency
            created_at = state_data.get('created_at')
            updated_at = state_data.get('updated_at')
            
            if created_at and updated_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                
                if updated_at < created_at:
                    temporal_issues.append("Updated timestamp is earlier than created timestamp")
            
            # Check deadline consistency
            deadline = state_data.get('deadline')
            if deadline:
                if isinstance(deadline, str):
                    deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                
                if deadline < datetime.utcnow():
                    temporal_issues.append("Deadline has passed")
            
            if temporal_issues:
                return ValidationStatus.FAILED, f"Temporal consistency issues: {', '.join(temporal_issues)}", {
                    'issues': temporal_issues
                }
            
            return ValidationStatus.PASSED, "Temporal consistency validated", {}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Temporal consistency validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_reference_integrity(self, workflow_id: str, state_data: Dict[str, Any],
                                   step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate reference integrity."""
        try:
            reference_issues = []
            
            # Check application references
            application_ids = state_data.get('application_ids', [])
            for app_id in application_ids:
                if not self._application_exists(app_id):
                    reference_issues.append(f"Application {app_id} does not exist")
            
            # Check vendor references
            vendor_ids = state_data.get('vendor_ids', [])
            for vendor_id in vendor_ids:
                if not self._vendor_exists(vendor_id):
                    reference_issues.append(f"Vendor {vendor_id} does not exist")
            
            # Check user references
            user_ids = state_data.get('user_ids', [])
            for user_id in user_ids:
                if not self._user_exists(user_id):
                    reference_issues.append(f"User {user_id} does not exist")
            
            if reference_issues:
                return ValidationStatus.FAILED, f"Reference integrity issues: {', '.join(reference_issues)}", {
                    'issues': reference_issues
                }
            
            return ValidationStatus.PASSED, "Reference integrity validated", {'references_checked': len(application_ids) + len(vendor_ids) + len(user_ids)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Reference integrity validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_performance_thresholds(self, workflow_id: str, state_data: Dict[str, Any],
                                       step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate performance thresholds."""
        try:
            performance_issues = []
            
            # Check execution time
            execution_time = state_data.get('execution_time', 0)
            max_execution_time = current_app.config.get('WORKFLOW_MAX_EXECUTION_TIME', 3600)  # 1 hour
            
            if execution_time > max_execution_time:
                performance_issues.append(f"Execution time ({execution_time}s) exceeds threshold ({max_execution_time}s)")
            
            # Check memory usage
            memory_usage = state_data.get('memory_usage_mb', 0)
            max_memory_usage = current_app.config.get('WORKFLOW_MAX_MEMORY_MB', 1024)  # 1GB
            
            if memory_usage > max_memory_usage:
                performance_issues.append(f"Memory usage ({memory_usage}MB) exceeds threshold ({max_memory_usage}MB)")
            
            # Check step count
            step_count = state_data.get('step_count', 0)
            max_steps = current_app.config.get('WORKFLOW_MAX_STEPS', 100)
            
            if step_count > max_steps:
                performance_issues.append(f"Step count ({step_count}) exceeds threshold ({max_steps})")
            
            if performance_issues:
                return ValidationStatus.FAILED, f"Performance threshold issues: {', '.join(performance_issues)}", {
                    'issues': performance_issues
                }
            
            return ValidationStatus.PASSED, "Performance thresholds within limits", {
                'execution_time': execution_time,
                'memory_usage': memory_usage,
                'step_count': step_count
            }
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Performance threshold validation failed: {str(e)}", {'error': str(e)}
    
    def _validate_data_quality(self, workflow_id: str, state_data: Dict[str, Any],
                             step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate data quality metrics."""
        try:
            quality_issues = []
            
            # Check for empty strings
            for key, value in state_data.items():
                if isinstance(value, str) and not value.strip():
                    quality_issues.append(f"Field {key} contains empty string")
            
            # Check for null values in critical fields
            critical_fields = ['workflow_id', 'status', 'created_at']
            null_critical_fields = [field for field in critical_fields if field in state_data and state_data[field] is None]
            
            if null_critical_fields:
                quality_issues.append(f"Critical fields with null values: {', '.join(null_critical_fields)}")
            
            # Check data consistency
            status = state_data.get('status')
            if status:
                valid_statuses = [
                    'pending',
                    'running',
                    'waiting_approval',
                    'completed',
                    'failed',
                    'cancelled',
                ]
                if status not in valid_statuses:
                    quality_issues.append(f"Invalid status value: {status}")
            
            if quality_issues:
                return ValidationStatus.FAILED, f"Data quality issues: {', '.join(quality_issues)}", {
                    'issues': quality_issues
                }
            
            return ValidationStatus.PASSED, "Data quality validated", {'fields_checked': len(state_data)}
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Data quality validation failed: {str(e)}", {'error': str(e)}
    
    def _default_validator(self, workflow_id: str, state_data: Dict[str, Any],
                          step_id: Optional[str] = None) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Default validator for custom rules."""
        return ValidationStatus.SKIPPED, "Custom validator not implemented", {}
    
    def _has_circular_references(self, data: Any, visited: Optional[set] = None) -> bool:
        """Check for circular references in data structure."""
        if visited is None:
            visited = set()
        
        if isinstance(data, dict):
            for key, value in data.items():
                if id(value) in visited:
                    return True
                visited.add(id(value))
                if self._has_circular_references(value, visited):
                    return True
        elif isinstance(data, list):
            for item in data:
                if id(item) in visited:
                    return True
                visited.add(id(item))
                if self._has_circular_references(item, visited):
                    return True
        
        return False
    
    def _is_resource_available(self, resource_name: str, resource_type: str) -> bool:
        """Check if a resource is available."""
        # Simulate resource availability check
        # In a real implementation, this would check actual resource status
        return True
    
    def _user_has_permissions(self, user_id: str, required_permissions: List[str]) -> bool:
        """Check if user has required permissions."""
        # Simulate permission check
        # In a real implementation, this would check actual user permissions
        return True
    
    def _application_exists(self, application_id: str) -> bool:
        """Check if application exists."""
        # Simulate application existence check
        # In a real implementation, this would query the database
        return True
    
    def _vendor_exists(self, vendor_id: str) -> bool:
        """Check if vendor exists."""
        # Simulate vendor existence check
        # In a real implementation, this would query the database
        return True
    
    def _user_exists(self, user_id: str) -> bool:
        """Check if user exists."""
        # Simulate user existence check
        # In a real implementation, this would query the database
        return True
    
    def get_validation_history(self, workflow_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get validation history for a workflow.
        
        Args:
            workflow_id: Workflow instance ID
            limit: Maximum number of results to return
            
        Returns:
            List of validation results
        """
        with self._lock:
            if workflow_id not in self._validation_history:
                return []
            
            history = self._validation_history[workflow_id][-limit:]
            
            return [result.to_dict() for result in history]
    
    def get_validation_summary(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get validation summary for a workflow.
        
        Args:
            workflow_id: Workflow instance ID
            
        Returns:
            Validation summary
        """
        with self._lock:
            history = self._validation_history.get(workflow_id, [])
        
        if not history:
            return {
                'workflow_id': workflow_id,
                'total_validations': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'average_execution_time': 0,
                'last_validation': None
            }
        
        # Calculate statistics
        total_validations = len(history)
        passed = len([r for r in history if r.status == ValidationStatus.PASSED])
        failed = len([r for r in history if r.status == ValidationStatus.FAILED])
        skipped = len([r for r in history if r.status == ValidationStatus.SKIPPED])
        
        avg_execution_time = sum(r.execution_time for r in history) / total_validations
        
        last_validation = history[-1]
        
        return {
            'workflow_id': workflow_id,
            'total_validations': total_validations,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'success_rate': passed / total_validations if total_validations > 0 else 0,
            'average_execution_time': avg_execution_time,
            'last_validation': last_validation.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a validation rule."""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = True
                logger.info(f"Enabled validation rule: {rule_id}")
                return True
            return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a validation rule."""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = False
                logger.info(f"Disabled validation rule: {rule_id}")
                return True
            return False
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all validation rules."""
        with self._lock:
            return [
                {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'severity': rule.severity.value,
                    'enabled': rule.enabled,
                    'category': rule.metadata.get('category', 'general')
                }
                for rule in self._rules.values()
            ]

# Global workflow state validator instance
workflow_state_validator = WorkflowStateValidator()
