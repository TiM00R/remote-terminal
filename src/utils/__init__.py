"""Utilities module"""

from .utils_text import (
    strip_ansi_codes, truncate_text, split_lines,
    extract_head_tail, count_lines, sanitize_output
)
from .utils_format import (
    format_duration, format_bytes, expand_path,
    timestamp_now, timestamp_local, format_command_prompt, Timer
)
from .utils_output import (
    is_error_output, extract_error_context,
    detect_command_type, parse_ls_output
)
from .utils_machine_id import fetch_machine_id_from_server

__all__ = [
    # Text utilities
    'strip_ansi_codes',
    'truncate_text',
    'split_lines',
    'extract_head_tail',
    'count_lines',
    'sanitize_output',
    # Format utilities
    'format_duration',
    'format_bytes',
    'expand_path',
    'timestamp_now',
    'timestamp_local',
    'format_command_prompt',
    'Timer',
    # Output utilities
    'is_error_output',
    'extract_error_context',
    'detect_command_type',
    'parse_ls_output',
    # Machine ID
    'fetch_machine_id_from_server'
]
