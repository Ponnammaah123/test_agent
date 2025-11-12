from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import json

def format_validation_errors(exc: RequestValidationError) -> dict:
    """
    Convert Pydantic validation errors to user-friendly format
    
    Args:
        exc: RequestValidationError from FastAPI/Pydantic
        
    Returns:
        Dictionary with custom error messages
    """
    errors = []
    
    for error in exc.errors():
        field = error['loc'][-1] if error['loc'] else 'unknown'
        error_type = error['type']
        
        # Map error types to user-friendly messages
        message_map = {
            'string_too_short': f"{field} cannot be empty",
            'string_too_long': f"{field} exceeds maximum length",
            'value_error': error.get('msg', f"Invalid value for {field}"),
            'missing': f"{field} is required",
            'greater_than': f"{field} must be greater than {error.get('ctx', {}).get('gt', 0)}",
            'less_than_equal': f"{field} must not exceed {error.get('ctx', {}).get('le', 100)}",
            'int_parsing': f"{field} must be an integer",
            'bool_parsing': f"{field} must be true or false",
            'string_pattern': f"{field} has invalid format",
        }
        
        # Use custom message or default Pydantic message
        message = message_map.get(error_type, error.get('msg', f"Invalid {field}"))
        
        # Add context-specific messages
        if error_type == 'value_error' and 'ctx' in error:
            # This is our custom validation error from @field_validator
            message = error.get('msg', message)
        
        errors.append({
            'field': field,
            'message': message,
            'type': error_type
        })
    
    return {
        'status': 'error',
        'code': 'VALIDATION_ERROR',
        'message': 'Request validation failed',
        'details': errors
    }


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for FastAPI RequestValidationError
    
    Converts Pydantic validation errors to HTTP 400 with custom format
    
    Args:
        request: FastAPI request
        exc: RequestValidationError
        
    Returns:
        JSONResponse with HTTP 400
    """
    error_response = format_validation_errors(exc)
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,  # Use 400 instead of 422
        content=error_response
    )


def add_validation_exception_handler(app: FastAPI):
    """
    Add custom validation error handler to FastAPI app
    
    Usage:
        app = FastAPI()
        add_validation_exception_handler(app)
        
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
