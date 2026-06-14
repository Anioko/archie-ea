"""
Import Validation Service

Provides comprehensive validation orchestration for import workflows.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from flask import current_app
from .csv_validator import csv_validator, ValidationStatus, ThreatLevel
from .data_integrity import data_integrity_checker, IntegrityCheckType
from .error_handler import import_error_handler, ImportError, ErrorCategory
from .rollback_manager import import_rollback_manager, RollbackType
from .import_audit import import_audit

logger = logging.getLogger(__name__)

@dataclass
class ImportValidationResult:
    """Represents the result of import validation."""
    status: str
    csv_validation: Dict[str, Any]
    integrity_checks: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    can_proceed: bool
    requires_manual_intervention: bool
    checkpoint_id: Optional[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'status': self.status,
            'csv_validation': self.csv_validation,
            'integrity_checks': self.integrity_checks,
            'errors': self.errors,
            'warnings': self.warnings,
            'can_proceed': self.can_proceed,
            'requires_manual_intervention': self.requires_manual_intervention,
            'checkpoint_id': self.checkpoint_id,
            'metadata': self.metadata
        }

class ImportValidationService:
    """
    Orchestrates comprehensive validation for import workflows.
    """
    
    def __init__(self):
        """Initialize the import validation service."""
        self._enabled = current_app.config.get('IMPORT_VALIDATION_ENABLED', True)
        self._strict_mode = current_app.config.get('IMPORT_VALIDATION_STRICT_MODE', False)
        
        logger.info(f"Import validation service initialized (enabled: {self._enabled}, strict_mode: {self._strict_mode})")
    
    def validate_import(self, csv_content: str, schema_name: str, import_id: str,
                      data: Optional[List[Dict[str, Any]]] = None) -> ImportValidationResult:
        """
        Perform comprehensive validation for an import.
        
        Args:
            csv_content: CSV content as string
            schema_name: Name of the schema to validate against
            import_id: Import session ID
            data: Parsed data rows (optional)
            
        Returns:
            Import validation result
        """
        if not self._enabled:
            return ImportValidationResult(
                status="validation_disabled",
                csv_validation={},
                integrity_checks=[],
                errors=[],
                warnings=[],
                can_proceed=True,
                requires_manual_intervention=False,
                checkpoint_id=None,
                metadata={'validation_enabled': False}
            )
        
        # Log validation start
        import_audit.log_validation_failed(import_id, [], user_id=None)
        
        errors = []
        warnings = []
        
        # Step 1: CSV Schema Validation
        try:
            csv_results = csv_validator.validate_csv(csv_content, schema_name)
            csv_summary = csv_validator.get_validation_summary(csv_results)
            
            # Categorize CSV validation results
            csv_errors = [r.to_dict() for r in csv_results if r.status == ValidationStatus.ERROR]
            csv_warnings = [r.to_dict() for r in csv_results if r.status == ValidationStatus.WARNING]
            
            errors.extend(csv_errors)
            warnings.extend(csv_warnings)
            
        except Exception as e:
            error_obj = import_error_handler.handle_error(e, context={'validation_type': 'csv_schema'})
            errors.append(error_obj.to_dict())
            csv_summary = {'total_results': 0, 'error_count': 1, 'warning_count': 0}
        
        # Step 2: Data Integrity Checks
        integrity_results = []
        if data:
            try:
                integrity_results = data_integrity_checker.check_integrity(data, schema_name)
                
                # Categorize integrity check results
                for result in integrity_results:
                    if result.status.value == 'failed':
                        errors.extend([issue.to_dict() for issue in result.issues_found])
                    elif result.status.value == 'warning':
                        warnings.extend([issue.to_dict() for issue in result.issues_found])
                
            except Exception as e:
                error_obj = import_error_handler.handle_error(e, context={'validation_type': 'data_integrity'})
                errors.append(error_obj.to_dict())
        
        # Step 3: Determine if import can proceed
        can_proceed = self._can_proceed_with_import(errors, warnings)
        requires_manual_intervention = self._requires_manual_intervention(errors, warnings)
        
        # Step 4: Create checkpoint if validation passes
        checkpoint_id = None
        if can_proceed and not requires_manual_intervention:
            try:
                checkpoint_id = import_rollback_manager.create_checkpoint(
                    import_id=import_id,
                    rollback_type=RollbackType.FULL_IMPORT,
                    state_data={
                        'csv_content': csv_content,
                        'schema_name': schema_name,
                        'validation_results': {
                            'csv_validation': csv_summary,
                            'integrity_checks': [r.to_dict() for r in integrity_results]
                        }
                    },
                    metadata={'validation_passed': True}
                )
            except Exception as e:
                logger.error(f"Failed to create validation checkpoint: {e}")
        
        # Step 5: Log validation completion
        import_audit.log_import_completed(
            import_id=import_id,
            duration=0,  # Would be calculated in real implementation
            records_processed=len(data) if data else 0,
            records_failed=len(errors),
            records_skipped=len(warnings),
            metadata={
                'validation_status': 'passed' if can_proceed else 'failed',
                'checkpoint_id': checkpoint_id
            }
        )
        
        # Determine overall status
        if not can_proceed:
            status = 'validation_failed'
        elif requires_manual_intervention:
            status = 'requires_intervention'
        elif warnings:
            status = 'validation_passed_with_warnings'
        else:
            status = 'validation_passed'
        
        return ImportValidationResult(
            status=status,
            csv_validation=csv_summary,
            integrity_checks=[r.to_dict() for r in integrity_results],
            errors=errors,
            warnings=warnings,
            can_proceed=can_proceed,
            requires_manual_intervention=requires_manual_intervention,
            checkpoint_id=checkpoint_id,
            metadata={
                'schema_name': schema_name,
                'validation_timestamp': datetime.utcnow().isoformat(),
                'strict_mode': self._strict_mode
            }
        )
    
    def _can_proceed_with_import(self, errors: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> bool:
        """Determine if import can proceed based on validation results."""
        if self._strict_mode:
            # In strict mode, any errors block the import
            return len(errors) == 0
        else:
            # In normal mode, only critical errors block the import
            critical_errors = [e for e in errors if e.get('severity') == 'critical']
            return len(critical_errors) == 0
    
    def _requires_manual_intervention(self, errors: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> bool:
        """Determine if manual intervention is required."""
        # Check for high severity issues
        high_severity_errors = [e for e in errors if e.get('severity') == 'high']
        high_severity_warnings = [w for w in warnings if w.get('severity') == 'high']
        
        # Check for specific error categories that require intervention
        intervention_errors = [e for e in errors if e.get('category') in ['referential_error', 'business_rule_error']]
        
        return (len(high_severity_errors) > 0 or 
                len(high_severity_warnings) > 3 or 
                len(intervention_errors) > 0)
    
    def get_available_schemas(self) -> List[str]:
        """Get list of available CSV schemas."""
        return csv_validator.get_available_schemas()
    
    def get_schema_definition(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Get schema definition by name."""
        schema = csv_validator.get_schema(schema_name)
        return schema.to_dict() if schema else None
    
    def validate_row(self, row_data: Dict[str, Any], schema_name: str, row_number: int) -> Dict[str, Any]:
        """
        Validate a single row against schema.
        
        Args:
            row_data: Row data dictionary
            schema_name: Schema name
            row_number: Row number
            
        Returns:
            Validation result for the row
        """
        try:
            schema = csv_validator.get_schema(schema_name)
            if not schema:
                return {
                    'valid': False,
                    'errors': [f"Schema '{schema_name}' not found"],
                    'warnings': []
                }
            
            # Convert row to CSV format for validation
            csv_content = ",".join(schema.required_columns + schema.optional_columns) + "\n"
            csv_content += ",".join([str(row_data.get(col, '')) for col in schema.required_columns + schema.optional_columns])
            
            results = csv_validator.validate_csv(csv_content, schema_name)
            
            # Filter results for this specific row
            row_results = [r for r in results if r.row_number == 1]  # Header is row 1, data is row 2
            
            return {
                'valid': len([r for r in row_results if r.status == ValidationStatus.ERROR]) == 0,
                'errors': [r.to_dict() for r in row_results if r.status == ValidationStatus.ERROR],
                'warnings': [r.to_dict() for r in row_results if r.status == ValidationStatus.WARNING]
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Row validation failed: {str(e)}"],
                'warnings': []
            }
    
    def get_validation_statistics(self, time_delta: Any = None) -> Dict[str, Any]:
        """
        Get comprehensive validation statistics.
        
        Args:
            time_delta: Time period to analyze (default: 24 hours)
            
        Returns:
            Validation statistics
        """
        if time_delta is None:
            from datetime import timedelta
            time_delta = timedelta(days=1)
        
        # Get statistics from all components
        csv_stats = {
            'available_schemas': self.get_available_schemas(),
            'schema_count': len(self.get_available_schemas())
        }
        
        integrity_stats = data_integrity_checker.get_integrity_summary([])
        
        error_stats = import_error_handler.get_error_statistics(time_delta)
        
        audit_stats = import_audit.get_audit_summary(time_delta)
        
        return {
            'time_period': f"{time_delta.days} days",
            'validation_enabled': self._enabled,
            'strict_mode': self._strict_mode,
            'csv_validation': csv_stats,
            'data_integrity': integrity_stats,
            'error_handling': error_stats,
            'audit_trail': audit_stats,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def update_configuration(self, config: Dict[str, Any]):
        """Update validation configuration."""
        if 'enabled' in config:
            self._enabled = config['enabled']
            logger.info(f"Import validation enabled: {self._enabled}")
        
        if 'strict_mode' in config:
            self._strict_mode = config['strict_mode']
            logger.info(f"Import validation strict mode: {self._strict_mode}")
        
        # Update component configurations
        if 'csv_validation' in config:
            csv_config = config['csv_validation']
            if 'allowed_mime_types' in csv_config:
                csv_validator.update_allowed_mime_types(csv_config['allowed_mime_types'])
            if 'blocked_extensions' in csv_config:
                csv_validator.update_blocked_extensions(csv_config['blocked_extensions'])
        
        if 'data_integrity' in config:
            integrity_config = config['data_integrity']
            if 'reference_data' in integrity_config:
                for ref_type, data in integrity_config['reference_data'].items():
                    data_integrity_checker.update_reference_data(ref_type, data)
        
        if 'error_handling' in config:
            # Update error handler configuration
            pass
        
        if 'rollback' in config:
            # Update rollback manager configuration
            pass
    
    def enable_strict_mode(self):
        """Enable strict validation mode."""
        self._strict_mode = True
        logger.warning("Import validation strict mode enabled")
    
    def disable_strict_mode(self):
        """Disable strict validation mode."""
        self._strict_mode = False
        logger.info("Import validation strict mode disabled")
    
    def enable_validation(self):
        """Enable import validation."""
        self._enabled = True
        logger.info("Import validation enabled")
    
    def disable_validation(self):
        """Disable import validation."""
        self._enabled = False
        logger.warning("Import validation disabled")

# Global import validation service instance
import_validation_service = ImportValidationService()
