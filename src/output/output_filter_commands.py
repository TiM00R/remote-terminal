"""
Command-Specific Output Filters
Smart filtering based on command type
"""

import logging
from utils.utils import extract_head_tail, parse_ls_output, format_bytes

logger = logging.getLogger(__name__)


def filter_installation(command: str, output: str, line_count: int) -> str:
    """
    Filter installation command output

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines

    Returns:
        Filtered output
    """
    # Installations can be very verbose, provide summary
    result = f"[Installation Output Summary]\n"
    result += f"Command: {command}\n"
    result += f"Total lines: {line_count}\n\n"

    # Get first and last few lines
    filtered, _, _ = extract_head_tail(output, 15, 15)
    result += filtered

    return result


def filter_file_listing(command: str, output: str, line_count: int) -> str:
    """
    Filter file listing output (ls, find, tree)

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines

    Returns:
        Filtered output
    """
    if 'ls' in command.lower() and ('-l' in command or '-la' in command):
        # Parse ls output for summary
        stats = parse_ls_output(output)

        result = f"[File Listing Summary]\n"
        result += f"Total items: {stats['total_items']}\n"
        result += f"Directories: {stats['directories']}\n"
        result += f"Files: {stats['files']}\n"
        result += f"Total size: {format_bytes(stats['total_size'])}\n\n"

        # Include first few entries
        filtered, _, _ = extract_head_tail(output, 20, 10)
        result += filtered

        return result

    # For other file listings, use truncation
    from .output_filter_decision import truncate_output
    return truncate_output(output)


def filter_file_viewing(command: str, output: str, line_count: int,
                       head_lines: int = 30, tail_lines: int = 20) -> str:
    """
    Filter file viewing output (cat, less, more)

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines
        head_lines: Number of head lines
        tail_lines: Number of tail lines

    Returns:
        Filtered output
    """
    result = f"[File Content]\n"
    result += f"Total lines: {line_count}\n\n"

    # Show head and tail
    filtered, _, _ = extract_head_tail(output, head_lines, tail_lines)
    result += filtered

    return result


def filter_system_info(command: str, output: str, line_count: int,
                       threshold: int) -> str:
    """
    Filter system info output (df, free, uptime)

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines
        threshold: System info threshold

    Returns:
        Filtered output
    """
    # System info is usually already concise, just truncate if too long
    if line_count <= threshold:
        return output

    from .output_filter_decision import truncate_output
    return truncate_output(output)


def filter_network_info(command: str, output: str, line_count: int) -> str:
    """
    Filter network info output

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines

    Returns:
        Filtered output
    """
    # Network info can be verbose, truncate
    from .output_filter_decision import truncate_output
    return truncate_output(output)


def filter_log_search(command: str, output: str, line_count: int) -> str:
    """
    Filter log search output (grep, awk, sed)

    Args:
        command: Command executed
        output: Full output
        line_count: Number of lines

    Returns:
        Filtered output
    """
    # Determine number of matches
    result = f"[Search Results]\n"
    result += f"Matches found: {line_count}\n"

    if line_count > 50:
        result += f"\nShowing first 25 and last 25 matches:\n\n"
        filtered, _, _ = extract_head_tail(output, 25, 25)
        result += filtered
    else:
        result += f"\n{output}"

    return result
