"""
Output Processing Utility Functions
Error detection, command type detection, and output parsing
"""

from typing import List
from .utils_text import split_lines


def is_error_output(text: str, error_patterns: List[str]) -> bool:
    """
    Check if text contains error patterns (context-aware)
    Uses improved error detection from error_check_helper

    Args:
        text: Text to check
        error_patterns: List of error patterns to look for

    Returns:
        True if error pattern found (with proper context)
    """
    # Use the improved context-aware error detection from error_check_helper
    from error_check_helper import check_for_errors

    error_summary = check_for_errors(text, error_patterns)
    return error_summary is not None


def extract_error_context(output: str, error_lines: int = 20) -> str:
    """
    Extract error context from command output

    Args:
        output: Full command output
        error_lines: Number of lines to include around error

    Returns:
        Error context
    """
    lines = split_lines(output)

    # Find lines with common error indicators
    error_indicators = ['error', 'failed', 'cannot', 'denied', 'fatal']
    error_line_indices = []

    for i, line in enumerate(lines):
        if any(indicator in line.lower() for indicator in error_indicators):
            error_line_indices.append(i)

    if not error_line_indices:
        # No specific error found, return last N lines
        return '\n'.join(lines[-error_lines:])

    # Get context around first error
    first_error = error_line_indices[0]
    start = max(0, first_error - error_lines // 2)
    end = min(len(lines), first_error + error_lines // 2)

    return '\n'.join(lines[start:end])


def detect_command_type(command: str) -> str:
    """
    Detect command type for smart filtering

    Args:
        command: Command string

    Returns:
        Command type identifier
    """
    command_lower = command.lower().strip()

    # Installation commands
    if any(cmd in command_lower for cmd in ['apt install', 'yum install', 'pip install', 'npm install']):
        return 'install'

    # System info commands
    if any(cmd in command_lower for cmd in ['df', 'free', 'uptime', 'uname', 'hostname']):
        return 'system_info'

    # Network commands
    if any(cmd in command_lower for cmd in ['ip addr', 'ip route', 'netstat', 'ss', 'ifconfig']):
        return 'network'

    # File listing
    if command_lower.startswith('ls') or command_lower.startswith('find') or 'tree' in command_lower:
        return 'file_listing'

    # File viewing
    if any(cmd in command_lower for cmd in ['cat', 'less', 'more', 'head', 'tail']):
        return 'file_viewing'

    # Log search
    if any(cmd in command_lower for cmd in ['grep', 'awk', 'sed']):
        return 'log_search'

    return 'generic'


def parse_ls_output(output: str) -> dict:
    """
    Parse ls -la output into structured data

    Args:
        output: ls command output

    Returns:
        Dictionary with file statistics
    """
    lines = split_lines(output)
    stats = {
        'total_items': 0,
        'directories': 0,
        'files': 0,
        'total_size': 0
    }

    for line in lines[1:]:  # Skip first line (total)
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) < 9:
            continue

        stats['total_items'] += 1

        # Check if directory (first char is 'd')
        if line.startswith('d'):
            stats['directories'] += 1
        else:
            stats['files'] += 1

        # Try to get file size (5th column)
        try:
            stats['total_size'] += int(parts[4])
        except (ValueError, IndexError):
            pass

    return stats
