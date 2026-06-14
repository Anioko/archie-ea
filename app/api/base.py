"""
API Base Classes and Utilities

Provides base resource classes and common functionality for Flask-RESTful APIs.
"""

from functools import wraps

from flask import current_app, jsonify, request
from flask_restful import Resource, abort
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db


def handle_errors(f):
    """
    Decorator for consistent error handling across all API resources.

    Returns standardized JSON responses for different error types.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error: {str(e)}")
            db.session.rollback()
            return {
                "error": "Database operation failed",
                "message": "See server logs for details",
                "type": "database_error",
            }, 500
        except ValueError as e:
            return {
                "error": "Invalid data provided",
                "message": "Invalid request parameters",
                "type": "validation_error",
            }, 400
        except KeyError as e:
            return {
                "error": "Missing required field",
                "message": "A required field is missing",
                "type": "missing_field_error",
            }, 400
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {str(e)}")
            return {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "type": "internal_error",
            }, 500

    return decorated_function


def validate_json_content_type(f):
    """
    Decorator to validate JSON content type for POST/PUT requests.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ["POST", "PUT"] and not request.is_json:
            return {
                "error": "Invalid content type",
                "message": "Content-Type must be application/json",
                "type": "content_type_error",
            }, 400
        return f(*args, **kwargs)

    return decorated_function


class BaseResource(Resource):
    """
    Base class for all API resources with common functionality.

    Provides:
    - Consistent error handling
    - JSON response formatting
    - Common CRUD operations
    - Serialization helpers
    """

    method_decorators = [handle_errors, validate_json_content_type]

    def __init__(self):
        super(BaseResource, self).__init__()
        self.model = None  # Override in subclasses

    def get_queryset(self):
        """
        Get the base queryset for this resource.
        Override in subclasses to add filters, ordering, etc.
        """
        if self.model is None:
            raise NotImplementedError("model must be set in subclass")
        return self.model.query

    def serialize(self, obj, many=False):
        """
        Convert model instance(s) to dictionary.
        Override in subclasses for custom serialization.
        """
        if many:
            return [self.serialize_single(item) for item in obj]
        return self.serialize_single(obj)

    def serialize_single(self, obj):
        """
        Serialize a single model instance.
        Override in subclasses for custom serialization.
        """
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        # Default serialization - convert to dict excluding private attributes
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    def get_object_or_404(self, id):
        """
        Get object by ID or return 404 response.
        """
        obj = self.model.query.get(id)
        if obj is None:
            abort(404, message=f"{self.model.__name__} with id {id} not found")
        return obj

    def parse_request_data(self):
        """
        Parse and validate JSON request data.
        """
        if not request.is_json:
            abort(400, message="Content-Type must be application/json")

        data = request.get_json()
        if data is None:
            abort(400, message="No JSON data provided")

        return data

    def create_object(self, data):
        """
        Create new object from request data.
        Override in subclasses for custom creation logic.
        """
        obj = self.model(**data)
        db.session.add(obj)
        db.session.commit()
        return obj

    def update_object(self, obj, data):
        """
        Update existing object with request data.
        Override in subclasses for custom update logic.
        """
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        db.session.commit()
        return obj

    def delete_object(self, obj):
        """
        Delete object from database.
        """
        db.session.delete(obj)
        db.session.commit()


class ModelResource(BaseResource):
    """
    Generic CRUD resource for SQLAlchemy models.

    Provides standard CRUD operations for any model with minimal configuration.
    """

    def __init__(self, model=None, exclude_fields=None, include_fields=None):
        super(ModelResource, self).__init__()
        self.model = model
        self.exclude_fields = exclude_fields or []
        self.include_fields = include_fields or []

    def get(self, id=None):
        """
        GET /resource - List all items
        GET /resource/<id> - Get single item
        """
        if id is None:
            # List all items
            queryset = self.get_queryset()
            items = queryset.all()
            return {"data": self.serialize(items, many=True), "count": len(items), "success": True}
        else:
            # Get single item
            obj = self.get_object_or_404(id)
            return {"data": self.serialize(obj), "success": True}

    def post(self):
        """
        POST /resource - Create new item
        """
        data = self.parse_request_data()

        # Filter data based on include/exclude fields
        filtered_data = self.filter_data(data)

        # Create object
        obj = self.create_object(filtered_data)

        return {
            "data": self.serialize(obj),
            "message": f"{self.model.__name__} created successfully",
            "success": True,
        }, 201

    def put(self, id):
        """
        PUT /resource/<id> - Update existing item
        """
        obj = self.get_object_or_404(id)
        data = self.parse_request_data()

        # Filter data based on include/exclude fields
        filtered_data = self.filter_data(data)

        # Update object
        obj = self.update_object(obj, filtered_data)

        return {
            "data": self.serialize(obj),
            "message": f"{self.model.__name__} updated successfully",
            "success": True,
        }

    def delete(self, id):
        """
        DELETE /resource/<id> - Delete item
        """
        obj = self.get_object_or_404(id)
        self.delete_object(obj)

        return {"message": f"{self.model.__name__} deleted successfully", "success": True}, 200

    def filter_data(self, data):
        """
        Filter request data based on include/exclude field lists.
        """
        if self.include_fields:
            # Only include specified fields
            return {k: v for k, v in data.items() if k in self.include_fields}
        elif self.exclude_fields:
            # Exclude specified fields
            return {k: v for k, v in data.items() if k not in self.exclude_fields}
        else:
            # No filtering
            return data


class PaginatedResource(BaseResource):
    """
    Resource with pagination support for large datasets.
    """

    def get(self, page=1, per_page=20):
        """
        GET /resource?page=1&per_page=20 - Get paginated list
        """
        from app.utils.pagination import get_pagination_params

        page, per_page = get_pagination_params(default_per_page=per_page, max_per_page=100)

        queryset = self.get_queryset()

        # Apply pagination
        pagination = queryset.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "data": self.serialize(pagination.items, many=True),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
            "success": True,
        }


class SearchableResource(BaseResource):
    """
    Resource with search functionality.
    """

    searchable_fields = []

    def get(self):
        """
        GET /resource?search=query - Search items
        """
        search_term = request.args.get("search", "").strip()

        if not search_term:
            # No search term, return all items
            return super(SearchableResource, self).get()

        if not self.searchable_fields:
            abort(400, message="No searchable fields configured")

        # Build search query
        queryset = self.get_queryset()
        search_filter = []

        for field in self.searchable_fields:
            if hasattr(self.model, field):
                search_filter.append(getattr(self.model, field).ilike(f"%{search_term}%"))

        if search_filter:
            from sqlalchemy import or_

            queryset = queryset.filter(or_(*search_filter))

        items = queryset.all()

        return {
            "data": self.serialize(items, many=True),
            "count": len(items),
            "search_term": search_term,
            "success": True,
        }


# Utility functions for creating resources dynamically
def create_model_resource(model_class, resource_name=None, **kwargs):
    """
    Factory function to create a ModelResource for a given model.

    Args:
        model_class: SQLAlchemy model class
        resource_name: Name for the resource class (optional)
        **kwargs: Additional arguments for ModelResource

    Returns:
        ModelResource class
    """
    if resource_name is None:
        resource_name = f"{model_class.__name__}Resource"

    class DynamicResource(ModelResource):
        model = model_class

        def __init__(self):
            super(DynamicResource, self).__init__(model_class, **kwargs)

    DynamicResource.__name__ = resource_name
    return DynamicResource
