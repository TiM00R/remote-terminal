"""
Output Filter Decision Logic
Determines whether to send output and handles error contexts
"""

import logging
from typing import List
from utils.utils import (
    count_lines, is_error_output, detect_command_type, extract_head_tail
)

logger = logging.getLogger(__name__)


def should_send_output(command: str, output: str, error_patterns: List[str],
                       thresholds: dict, auto_send_errors: bool) -> bool:
    """
    Determine if output should be sent to Claude

    Args:
        command: Command that was executed
        output: Command output
        error_patterns: List of error patterns to detect
        thresholds: Line thresholds for different command types
        auto_send_errors: Auto send error output to Claude

    Returns:
        True if should send to Claude
    """
    # Always send errors
    if auto_send_errors and is_error_output(output, error_patterns):
        logger.debug("Output contains errors, will send to Claude")
        return True

    # Check command type and line count
    cmd_type = detect_command_type(command)
    line_count = count_lines(output)
    threshold = thresholds.get(cmd_type, thresholds['generic'])

    # Don't send very verbose output
    if line_count > threshold * 2:
        logger.debug(f"Output too verbose ({line_count} lines), will not auto-send")
        return False

    return True


def filter_with_errors(command: str, output: str, cmd_type: str,
                       error_patterns: List[str]) -> str:
    """
    Filter output that contains errors

    Args:
        command: Command executed
        output: Full output
        cmd_type: Command type
        error_patterns: List of error patterns

    Returns:
        Filtered output with error context
    """
    lines = output.split('\n')

    # Find error lines
    error_indices = []
    for i, line in enumerate(lines):
        if is_error_output(line, error_patterns):
            error_indices.append(i)

    if not error_indices:
        # No specific error found, return last portion
        return truncate_output(output, head_lines=30, tail_lines=20)

    # Get context around first error
    first_error = error_indices[0]
    context_lines = 10
    start = max(0, first_error - context_lines)
    end = min(len(lines), first_error + context_lines)

    error_context = '\n'.join(lines[start:end])

    result = f"[Error detected in command output]\n"
    result += f"Command: {command}\n"
    result += f"Total output lines: {len(lines)}\n"
    result += f"\nError context:\n{error_context}"

    return result


def truncate_output(output: str, head_lines: int = 30, tail_lines: int = 20) -> str:
    """
    Generic truncation for any output

    Args:
        output: Full output
        head_lines: Number of head lines
        tail_lines: Number of tail lines

    Returns:
        Truncated output
    """
    filtered, total_lines, was_truncated = extract_head_tail(
        output,
        head_lines,
        tail_lines
    )

    if was_truncated:
        result = f"[Output truncated - {total_lines} total lines]\n\n"
        result += filtered
        return result

    return output
