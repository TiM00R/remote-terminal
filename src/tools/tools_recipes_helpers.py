"""
Recipe Helper Functions
Utility functions for recipe management
"""


def _convert_datetimes_to_strings(obj):
    """Recursively convert all datetime objects to strings"""
    from datetime import datetime

    if isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: _convert_datetimes_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes_to_strings(item) for item in obj]
    else:
        return obj
