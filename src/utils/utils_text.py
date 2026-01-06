"""
Text Utility Functions
ANSI code handling, text processing, and line manipulation
"""

import re
from typing import List, Tuple


def strip_ansi_codes(text: str) -> str:
    """
    Remove ANSI escape codes from text

    Args:
        text: Text containing ANSI codes

    Returns:
        Clean text without ANSI codes
    """
    # Remove OSC sequences (Operating System Command) like terminal titles
    # Pattern: ESC ] number ; text BEL
    # The "0;" at the start of prompt is from this
    text = re.sub(r'\x1B\]0;[^\x07]*\x07', '', text)
    text = re.sub(r'\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)', '', text)

    # Remove CSI sequences (colors, cursor movement, etc.)
    # Pattern: ESC [ parameters letter
    text = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)

    # Remove other escape sequences
    text = re.sub(r'\x1B[@-Z\\-_]', '', text)

    # Remove bell character
    text = text.replace('\x07', '')

    # Remove any remaining control characters except newline, tab, carriage return
    # This will catch any stray escape sequences we missed
    cleaned = []
    for char in text:
        code = ord(char)
        if code >= 32 or char in '\n\t\r':
            cleaned.append(char)

    return ''.join(cleaned)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def split_lines(text: str) -> List[str]:
    """
    Split text into lines, handling different line endings

    Args:
        text: Text to split

    Returns:
        List of lines
    """
    # Handle \r\n, \r, and \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text.split('\n')


def extract_head_tail(text: str, head_lines: int = 30, tail_lines: int = 20) -> Tuple[str, int, bool]:
    """
    Extract head and tail lines from text

    Args:
        text: Full text
        head_lines: Number of lines from start
        tail_lines: Number of lines from end

    Returns:
        Tuple of (extracted_text, total_lines, was_truncated)
    """
    lines = split_lines(text)
    total = len(lines)

    if total <= (head_lines + tail_lines):
        return text, total, False

    head = '\n'.join(lines[:head_lines])
    tail = '\n'.join(lines[-tail_lines:])
    omitted = total - head_lines - tail_lines

    result = f"{head}\n\n[... {omitted} lines omitted ...]\n\n{tail}"
    return result, total, True


def count_lines(text: str) -> int:
    """
    Count number of lines in text

    Args:
        text: Text to count

    Returns:
        Number of lines
    """
    return len(split_lines(text))


def sanitize_output(text: str) -> str:
    """
    Sanitize output for safe display

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove other control characters except newline, tab, carriage return
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')

    return text
