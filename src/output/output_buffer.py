"""
Output Buffer - Terminal output management
Split into modules for better organization
"""

# Import from split modules
from .output_buffer_base import (
    OutputLine,
    OutputBuffer
)
from .output_buffer_filtered import (
    FilteredBuffer
)

# Re-export all classes for backward compatibility
__all__ = [
    'OutputLine',
    'OutputBuffer',
    'FilteredBuffer'
]
