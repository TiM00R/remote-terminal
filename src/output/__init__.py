"""Output handling module"""

from .output_buffer import OutputLine, OutputBuffer, FilteredBuffer
from .output_buffer_base import OutputLine as OutputLineBase, OutputBuffer as OutputBufferBase
from .output_buffer_filtered import FilteredBuffer as FilteredBufferImpl
from .output_filter import SmartOutputFilter
from .output_filter_commands import (
    filter_installation, filter_file_listing, filter_file_viewing,
    filter_system_info, filter_network_info, filter_log_search
)
from .output_filter_decision import should_send_output, filter_with_errors, truncate_output
from .output_formatter import find_errors_with_context, format_output

__all__ = [
    'OutputLine',
    'OutputBuffer',
    'FilteredBuffer',
    'SmartOutputFilter',
    'filter_installation',
    'filter_file_listing',
    'filter_file_viewing',
    'filter_system_info',
    'filter_network_info',
    'filter_log_search',
    'should_send_output',
    'filter_with_errors',
    'truncate_output',
    'find_errors_with_context',
    'format_output'
]
