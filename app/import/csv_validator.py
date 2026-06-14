"""
CSV Validator

Provides comprehensive CSV schema validation for import workflows.
"""

import logging
import csv
import io
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import re

from flask import current_app

logger = logging.getLogger(__name__)

class ValidationStatus(Enum):
    """Validation status levels."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    ERROR = "error"

class DataType(Enum):
    """Supported data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    CUSTOM = "custom"

@dataclass
class ColumnDefinition:
    """Defines a column in the CSV schema."""
    name: str
    data_type: DataType
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    unique: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert column definition to dictionary."""
        return {
            'name': self.name,
            'data_type': self.data_type.value,
            'required': self.required,
            'min_length': self.min_length,
            'max_length': self.max_length,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'pattern': self.pattern,
            'allowed_values': self.allowed_values,
            'unique': self.unique,
            'default_value': self.default_value,
            'description': self.description
        }

@dataclass
class ValidationResult:
    """Represents a validation result."""
    status: ValidationStatus
    row_number: Optional[int]
    column_name: Optional[str]
    value: Optional[str]
    message: str
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            'status': self.status.value,
            'row_number': self.row_number,
            'column_name': self.column_name,
            'value': self.value,
            'message': self.message,
            'details': self.details
        }

@dataclass
class CSVSchema:
    """Defines a CSV schema."""
    name: str
    version: str
    description: str
    columns: List[ColumnDefinition]
    required_columns: List[str]
    optional_columns: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'columns': [col.to_dict() for col in self.columns],
            'required_columns': self.required_columns,
            'optional_columns': self.optional_columns,
            'metadata': self.metadata
        }

class CSVValidator:
    """
    Validates CSV files against defined schemas.
    """
    
    def __init__(self):
        """Initialize the CSV validator."""
        self._schemas = {}
        self._default_schemas = {}
        
        # Initialize default schemas
        self._initialize_default_schemas()
        
        # Load custom schemas from configuration
        self._load_custom_schemas()
    
    def _initialize_default_schemas(self):
        """Initialize default CSV schemas."""
        # Application import schema
        self._default_schemas['application_import'] = CSVSchema(
            name='application_import',
            version='1.0',
            description='Schema for application data import',
            columns=[
                ColumnDefinition('application_name', DataType.STRING, required=True, max_length=255),
                ColumnDefinition('description', DataType.STRING, required=False, max_length=1000),
                ColumnDefinition('owner', DataType.STRING, required=True, max_length=255),
                ColumnDefinition('business_unit', DataType.STRING, required=True, max_length=100),
                ColumnDefinition('status', DataType.STRING, required=True, allowed_values=['active', 'inactive', 'pending']),
                ColumnDefinition('priority', DataType.STRING, required=False, allowed_values=['high', 'medium', 'low']),
                ColumnDefinition('created_date', DataType.DATE, required=False),
                ColumnDefinition('cost_center', DataType.STRING, required=False, max_length=50),
            ],
            required_columns=['application_name', 'owner', 'business_unit', 'status'],
            optional_columns=['description', 'priority', 'created_date', 'cost_center'],
            metadata={'category': 'application'}
        )
        
        # Vendor import schema
        self._default_schemas['vendor_import'] = CSVSchema(
            name='vendor_import',
            version='1.0',
            description='Schema for vendor data import',
            columns=[
                ColumnDefinition('vendor_name', DataType.STRING, required=True, max_length=255),
                ColumnDefinition('contact_email', DataType.EMAIL, required=True),
                ColumnDefinition('phone', DataType.PHONE, required=False),
                ColumnDefinition('website', DataType.URL, required=False),
                ColumnDefinition('category', DataType.STRING, required=True, allowed_values=['software', 'hardware', 'services', 'consulting']),
                ColumnDefinition('rating', DataType.STRING, required=False, allowed_values=['A', 'B', 'C', 'D']),
                ColumnDefinition('active', DataType.BOOLEAN, required=True),
                ColumnDefinition('contract_value', DataType.FLOAT, required=False, min_value=0),
            ],
            required_columns=['vendor_name', 'contact_email', 'category', 'active'],
            optional_columns=['phone', 'website', 'rating', 'contract_value'],
            metadata={'category': 'vendor'}
        )
        
        # User import schema
        self._default_schemas['user_import'] = CSVSchema(
            name='user_import',
            version='1.0',
            description='Schema for user data import',
            columns=[
                ColumnDefinition('username', DataType.STRING, required=True, max_length=50, pattern=r'^[a-zA-Z0-9_]+$'),
                ColumnDefinition('email', DataType.EMAIL, required=True),
                ColumnDefinition('first_name', DataType.STRING, required=True, max_length=100),
                ColumnDefinition('last_name', DataType.STRING, required=True, max_length=100),
                ColumnDefinition('role', DataType.STRING, required=True, allowed_values=['admin', 'user', 'viewer']),
                ColumnDefinition('department', DataType.STRING, required=True, max_length=100),
                ColumnDefinition('active', DataType.BOOLEAN, required=True),
                ColumnDefinition('last_login', DataType.DATETIME, required=False),
            ],
            required_columns=['username', 'email', 'first_name', 'last_name', 'role', 'department', 'active'],
            optional_columns=['last_login'],
            metadata={'category': 'user'}
        )
        
        # Add default schemas to available schemas
        self._schemas.update(self._default_schemas)
    
    def _load_custom_schemas(self):
        """Load custom schemas from configuration."""
        try:
            custom_schemas = current_app.config.get('CSV_IMPORT_SCHEMAS', {})
            
            for schema_name, schema_config in custom_schemas.items():
                columns = []
                
                for col_config in schema_config.get('columns', []):
                    column = ColumnDefinition(
                        name=col_config['name'],
                        data_type=DataType(col_config.get('data_type', 'string')),
                        required=col_config.get('required', True),
                        min_length=col_config.get('min_length'),
                        max_length=col_config.get('max_length'),
                        min_value=col_config.get('min_value'),
                        max_value=col_config.get('max_value'),
                        pattern=col_config.get('pattern'),
                        allowed_values=col_config.get('allowed_values'),
                        unique=col_config.get('unique', False),
                        default_value=col_config.get('default_value'),
                        description=col_config.get('description')
                    )
                    columns.append(column)
                
                schema = CSVSchema(
                    name=schema_name,
                    version=schema_config.get('version', '1.0'),
                    description=schema_config.get('description', ''),
                    columns=columns,
                    required_columns=schema_config.get('required_columns', []),
                    optional_columns=schema_config.get('optional_columns', []),
                    metadata=schema_config.get('metadata', {})
                )
                
                self._schemas[schema_name] = schema
                
        except Exception as e:
            logger.warning(f"Failed to load custom schemas: {e}")
    
    def validate_csv(self, csv_content: str, schema_name: str) -> List[ValidationResult]:
        """
        Validate CSV content against a schema.
        
        Args:
            csv_content: CSV content as string
            schema_name: Name of the schema to validate against
            
        Returns:
            List of validation results
        """
        results = []
        
        # Get schema
        schema = self._schemas.get(schema_name)
        if not schema:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=None,
                column_name=None,
                value=None,
                message=f"Schema '{schema_name}' not found",
                details={'available_schemas': list(self._schemas.keys())}
            ))
            return results
        
        try:
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Validate header
            header_validation = self._validate_header(csv_reader.fieldnames, schema)
            results.extend(header_validation)
            
            # Check for critical header errors
            critical_header_errors = [r for r in header_validation if r.status == ValidationStatus.ERROR]
            if critical_header_errors:
                return results
            
            # Validate each row
            for row_num, row in enumerate(csv_reader, 1):
                row_results = self._validate_row(row, row_num, schema)
                results.extend(row_results)
            
            # Validate overall data consistency
            consistency_results = self._validate_data_consistency(csv_content, schema)
            results.extend(consistency_results)
            
        except Exception as e:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=None,
                column_name=None,
                value=None,
                message=f"CSV parsing error: {str(e)}",
                details={'error': str(e)}
            ))
        
        return results
    
    def _validate_header(self, header: List[str], schema: CSVSchema) -> List[ValidationResult]:
        """Validate CSV header against schema."""
        results = []
        
        # Check for missing required columns
        missing_columns = set(schema.required_columns) - set(header)
        for col in missing_columns:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=1,
                column_name=col,
                value=None,
                message=f"Required column '{col}' is missing",
                details={'missing_columns': list(missing_columns)}
            ))
        
        # Check for unknown columns
        known_columns = set(schema.required_columns + schema.optional_columns)
        unknown_columns = set(header) - known_columns
        for col in unknown_columns:
            results.append(ValidationResult(
                status=ValidationStatus.WARNING,
                row_number=1,
                column_name=col,
                value=None,
                message=f"Unknown column '{col}' found",
                details={'unknown_columns': list(unknown_columns)}
            ))
        
        # Check for duplicate columns
        duplicate_columns = [col for col in header if header.count(col) > 1]
        for col in set(duplicate_columns):
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=1,
                column_name=col,
                value=None,
                message=f"Duplicate column '{col}' found",
                details={'duplicate_columns': duplicate_columns}
            ))
        
        return results
    
    def _validate_row(self, row: Dict[str, str], row_num: int, schema: CSVSchema) -> List[ValidationResult]:
        """Validate a single CSV row."""
        results = []
        
        # Get column definitions
        column_defs = {col.name: col for col in schema.columns}
        
        for column_name, value in row.items():
            # Skip unknown columns
            if column_name not in column_defs:
                continue
            
            column_def = column_defs[column_name]
            
            # Validate value
            value_results = self._validate_value(value, column_def, row_num, column_name)
            results.extend(value_results)
        
        # Check for missing required values
        for column_def in schema.columns:
            if column_def.required and column_def.name not in row:
                results.append(ValidationResult(
                    status=ValidationStatus.ERROR,
                    row_number=row_num,
                    column_name=column_def.name,
                    value=None,
                    message=f"Required value missing for column '{column_def.name}'",
                    details={'column': column_def.name}
                ))
        
        return results
    
    def _validate_value(self, value: str, column_def: ColumnDefinition, 
                        row_num: int, column_name: str) -> List[ValidationResult]:
        """Validate a single value against column definition."""
        results = []
        
        # Handle empty values
        if not value or value.strip() == '':
            if column_def.required:
                results.append(ValidationResult(
                    status=ValidationStatus.ERROR,
                    row_number=row_num,
                    column_name=column_name,
                    value=value,
                    message=f"Required value cannot be empty",
                    details={'column': column_name}
                ))
            return results
        
        value = value.strip()
        
        # Validate based on data type
        type_validation = self._validate_data_type(value, column_def, row_num, column_name)
        results.extend(type_validation)
        
        # Validate length constraints
        if column_def.min_length and len(value) < column_def.min_length:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=row_num,
                column_name=column_name,
                value=value,
                message=f"Value too short (min: {column_def.min_length})",
                details={'min_length': column_def.min_length, 'actual_length': len(value)}
            ))
        
        if column_def.max_length and len(value) > column_def.max_length:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=row_num,
                column_name=column_name,
                value=value,
                message=f"Value too long (max: {column_def.max_length})",
                details={'max_length': column_def.max_length, 'actual_length': len(value)}
            ))
        
        # Validate value constraints
        if column_def.min_value is not None:
            try:
                numeric_value = float(value)
                if numeric_value < column_def.min_value:
                    results.append(ValidationResult(
                        status=ValidationStatus.ERROR,
                        row_number=row_num,
                        column_name=column_name,
                        value=value,
                        message=f"Value below minimum ({column_def.min_value})",
                        details={'min_value': column_def.min_value, 'actual_value': numeric_value}
                    ))
            except ValueError:
                pass  # Already handled in data type validation
        
        if column_def.max_value is not None:
            try:
                numeric_value = float(value)
                if numeric_value > column_def.max_value:
                    results.append(ValidationResult(
                        status=ValidationStatus.ERROR,
                        row_number=row_num,
                        column_name=column_name,
                        value=value,
                        message=f"Value above maximum ({column_def.max_value})",
                        details={'max_value': column_def.max_value, 'actual_value': numeric_value}
                    ))
            except ValueError:
                pass  # Already handled in data type validation
        
        # Validate pattern
        if column_def.pattern:
            if not re.match(column_def.pattern, value):
                results.append(ValidationResult(
                    status=ValidationStatus.ERROR,
                    row_number=row_num,
                    column_name=column_name,
                    value=value,
                    message=f"Value does not match required pattern",
                    details={'pattern': column_def.pattern}
                ))
        
        # Validate allowed values
        if column_def.allowed_values and value not in column_def.allowed_values:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=row_num,
                column_name=column_name,
                value=value,
                message=f"Value not in allowed values",
                details={'allowed_values': column_def.allowed_values, 'actual_value': value}
            ))
        
        return results
    
    def _validate_data_type(self, value: str, column_def: ColumnDefinition, 
                           row_num: int, column_name: str) -> List[ValidationResult]:
        """Validate value data type."""
        results = []
        
        try:
            if column_def.data_type == DataType.STRING:
                # String is always valid
                pass
            
            elif column_def.data_type == DataType.INTEGER:
                int(value)
            
            elif column_def.data_type == DataType.FLOAT:
                float(value)
            
            elif column_def.data_type == DataType.BOOLEAN:
                if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no', 'y', 'n']:
                    raise ValueError("Invalid boolean value")
            
            elif column_def.data_type == DataType.DATE:
                # Try multiple date formats
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
                parsed = False
                for fmt in date_formats:
                    try:
                        datetime.strptime(value, fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                if not parsed:
                    raise ValueError("Invalid date format")
            
            elif column_def.data_type == DataType.DATETIME:
                # Try multiple datetime formats
                datetime_formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M:%S']
                parsed = False
                for fmt in datetime_formats:
                    try:
                        datetime.strptime(value, fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                if not parsed:
                    raise ValueError("Invalid datetime format")
            
            elif column_def.data_type == DataType.EMAIL:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, value):
                    raise ValueError("Invalid email format")
            
            elif column_def.data_type == DataType.URL:
                url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
                if not re.match(url_pattern, value):
                    raise ValueError("Invalid URL format")
            
            elif column_def.data_type == DataType.PHONE:
                # Simple phone validation
                phone_pattern = r'^\+?[\d\s\-\(\)]{10,}$'
                if not re.match(phone_pattern, value):
                    raise ValueError("Invalid phone format")
            
            elif column_def.data_type == DataType.CUSTOM:
                # Custom validation would be implemented here
                pass
            
        except ValueError as e:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=row_num,
                column_name=column_name,
                value=value,
                message=f"Invalid {column_def.data_type.value}: {str(e)}",
                details={'expected_type': column_def.data_type.value}
            ))
        
        return results
    
    def _validate_data_consistency(self, csv_content: str, schema: CSVSchema) -> List[ValidationResult]:
        """Validate overall data consistency."""
        results = []
        
        try:
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            
            # Check for unique constraints
            for column_def in schema.columns:
                if column_def.unique:
                    unique_values = set()
                    for row_num, row in enumerate(csv_reader, 1):
                        if column_def.name in row:
                            value = row[column_def.name]
                            if value in unique_values:
                                results.append(ValidationResult(
                                    status=ValidationStatus.ERROR,
                                    row_number=row_num,
                                    column_name=column_def.name,
                                    value=value,
                                    message=f"Duplicate value in unique column",
                                    details={'first_occurrence': list(unique_values).index(value) + 1}
                                ))
                            else:
                                unique_values.add(value)
                    
                    # Reset reader for next column
                    csv_content.seek(0)
                    csv_reader = csv.DictReader(io.StringIO(csv_content))
            
        except Exception as e:
            results.append(ValidationResult(
                status=ValidationStatus.ERROR,
                row_number=None,
                column_name=None,
                value=None,
                message=f"Data consistency check failed: {str(e)}",
                details={'error': str(e)}
            ))
        
        return results
    
    def get_schema(self, schema_name: str) -> Optional[CSVSchema]:
        """Get a schema by name."""
        return self._schemas.get(schema_name)
    
    def get_available_schemas(self) -> List[str]:
        """Get list of available schemas."""
        return list(self._schemas.keys())
    
    def add_schema(self, schema: CSVSchema):
        """Add a new schema."""
        self._schemas[schema.name] = schema
        logger.info(f"Added CSV schema: {schema.name}")
    
    def remove_schema(self, schema_name: str) -> bool:
        """Remove a schema."""
        if schema_name in self._schemas:
            del self._schemas[schema_name]
            logger.info(f"Removed CSV schema: {schema_name}")
            return True
        return False
    
    def get_validation_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Get summary of validation results.
        
        Args:
            results: List of validation results
            
        Returns:
            Validation summary
        """
        total_results = len(results)
        error_count = len([r for r in results if r.status == ValidationStatus.ERROR])
        warning_count = len([r for r in results if r.status == ValidationStatus.WARNING])
        valid_count = len([r for r in results if r.status == ValidationStatus.VALID])
        
        # Group by column
        column_issues = {}
        for result in results:
            if result.column_name:
                column = result.column_name
                if column not in column_issues:
                    column_issues[column] = {'error': 0, 'warning': 0, 'valid': 0}
                column_issues[column][result.status.value] += 1
        
        # Group by row
        row_issues = {}
        for result in results:
            if result.row_number:
                row = result.row_number
                if row not in row_issues:
                    row_issues[row] = {'error': 0, 'warning': 0, 'valid': 0}
                row_issues[row][result.status.value] += 1
        
        return {
            'total_results': total_results,
            'error_count': error_count,
            'warning_count': warning_count,
            'valid_count': valid_count,
            'success_rate': valid_count / total_results if total_results > 0 else 0,
            'column_issues': column_issues,
            'row_issues': row_issues,
            'timestamp': datetime.utcnow().isoformat()
        }

# Global CSV validator instance
csv_validator = CSVValidator()
