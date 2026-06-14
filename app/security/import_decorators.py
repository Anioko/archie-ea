"""
Import Security Decorators

Security decorators specifically for import functionality.
Provides CSP headers and other security measures for import pages.
"""

from functools import wraps
from flask import current_app, request


def with_import_security(f):
    """
    Decorator to apply import-specific security headers to routes.
    
    This decorator adds Content-Security-Policy headers specifically
    configured for import functionality, balancing security with
    the dynamic JavaScript requirements of import interfaces.
    
    Usage:
        @with_import_security
        @login_required
        def import_page():
            return render_template('batch_import/new_import.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the response from the original function
        response = f(*args, **kwargs)
        
        # Apply import-specific CSP if configured
        import_csp = current_app.config.get("IMPORT_CONTENT_SECURITY_POLICY")
        if import_csp and hasattr(response, 'headers'):
            response.headers["Content-Security-Policy"] = import_csp
            
            # Log CSP application for debugging
            current_app.logger.debug(
                f"Applied import CSP to {request.endpoint if request else 'unknown route'}"
            )
        
        return response
    
    return decorated_function


def csp_headers_for_import(response):
    """
    Function to apply CSP headers to a response object.
    
    Alternative to decorator when you need more control over
    when CSP headers are applied.
    
    Args:
        response: Flask response object
        
    Returns:
        Response with CSP headers applied
    """
    import_csp = current_app.config.get("IMPORT_CONTENT_SECURITY_POLICY")
    if import_csp and hasattr(response, 'headers'):
        response.headers["Content-Security-Policy"] = import_csp
        
        current_app.logger.debug("Applied import CSP headers to response")
    
    return response
