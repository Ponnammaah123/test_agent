# ==============================================
# Common utility functions
# ==============================================

from typing import Optional, Dict, Any
import json

def safe_get(dictionary: Dict, *keys, default=None) -> Any:
    """
    Safely get nested dictionary values
    
    Example:
        safe_get(data, 'user', 'profile', 'name', default='Unknown')
    """
    result = dictionary
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None:
                return default
        else:
            return default
    return result if result is not None else default

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def format_json(data: Any, indent: int = 2) -> str:
    """Format data as pretty JSON string"""
    try:
        return json.dumps(data, indent=indent, default=str)
    except:
        return str(data)