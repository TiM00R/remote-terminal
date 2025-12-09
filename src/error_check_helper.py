import re


def is_installation_command(command: str, summary_mode_commands: list) -> bool:
    """Check if command is an installation/build command"""
    command_lower = command.lower()
    return any(cmd_pattern in command_lower for cmd_pattern in summary_mode_commands)


def is_file_listing_line(line: str) -> bool:
    """
    Detect if a line is from file listing commands (ls, ll, dir, etc.)
    
    Returns:
        True if line looks like a file/directory listing
    """
    line_stripped = line.strip()
    
    # Empty lines or very short lines
    if len(line_stripped) < 10:
        return False
    
    # Check for Unix file listing pattern: permissions + links + owner + group + size + date + filename
    # Example: -rw-r--r--  1 user group  1234 Nov 12 10:30 filename
    # Example: drwxr-xr-x  5 user group  4096 Nov 12 10:30 dirname
    file_listing_pattern = r'^[dlrwxst-]{10}\s+\d+\s+\S+\s+\S+\s+\d+\s+\w+\s+\d+\s+'
    
    if re.match(file_listing_pattern, line_stripped):
        return True
    
    # Check for total line from ls -l
    if re.match(r'^total\s+\d+', line_stripped.lower()):
        return True
    
    return False


def has_error_context(line: str, pattern: str) -> bool:
    """
    Check if error pattern appears in proper error context (not just in filenames)
    
    Args:
        line: Line to check
        pattern: Error pattern to look for
        
    Returns:
        True if this is likely a real error, False if likely false positive
    """
    line_lower = line.lower()
    pattern_lower = pattern.lower()
    
    # Pattern not in line at all
    if pattern_lower not in line_lower:
        return False
    
    # Skip if this looks like a file listing
    if is_file_listing_line(line):
        return False
    
    # Look for error indicators that suggest real errors
    error_indicators = [
        f'{pattern_lower}:',      # error:, failed:, etc.
        f'[{pattern_lower}]',     # [error], [failed]
        f'({pattern_lower})',     # (error), (failed)
        f'{pattern_lower} -',     # error -, failed -
        f'{pattern_lower}!',      # error!, failed!
    ]
    
    # Check if pattern appears with error indicators
    for indicator in error_indicators:
        if indicator in line_lower:
            return True
    
    # Check for word boundary - pattern is a complete word, not substring
    # Use regex word boundary \b to ensure it's not part of a filename
    word_boundary_pattern = r'\b' + re.escape(pattern_lower) + r'\b'
    if re.search(word_boundary_pattern, line_lower):
        # Found as complete word, now check if it's likely a filename
        
        # Common false positive patterns to skip
        false_positive_patterns = [
            r'\.(log|txt|err|errors)$',           # .log, .txt, .err files
            r'\.x?session-errors',                # .xsession-errors, .session-errors
            r'error[-_]?(log|file|dump)',         # error-log, error_file, etc.
            r'/(var|tmp|log)/.*error',            # paths like /var/log/error
            r'error[-_]?\w+\.(py|sh|txt|log)',   # error_handler.py, error.log
        ]
        
        for fp_pattern in false_positive_patterns:
            if re.search(fp_pattern, line_lower):
                return False  # Skip common filename patterns
        
        # If we get here, it's a word boundary match and not a known filename pattern
        # Check if line has other error-like characteristics
        
        # Lines that start with error/failed are usually real errors
        if re.match(r'^\s*' + word_boundary_pattern, line_lower):
            return True
        
        # Lines with multiple error indicators
        error_words = ['error', 'fail', 'failed', 'exception', 'fatal', 'critical']
        error_count = sum(1 for word in error_words if re.search(r'\b' + word + r'\b', line_lower))
        if error_count >= 2:
            return True
        
        # Check if surrounded by error context words
        context_words = ['cannot', 'unable', 'denied', 'not found', 'invalid', 'missing', 'refused']
        if any(re.search(r'\b' + word + r'\b', line_lower) for word in context_words):
            return True
    
    # Default: if we can't determine, don't flag it (reduce false positives)
    return False


def check_for_errors(output: str, error_patterns: list):
    """
    Scan full output for error patterns with context awareness
    Always checks regardless of output mode
    
    Improved version: Reduces false positives from filenames and file listings
    
    Args:
        output: Full command output
        error_patterns: List of error patterns to detect
        
    Returns:
        Error summary string or None if no errors found
    """
    if not output or not output.strip():
        return None
    
    lines = output.split('\n')
    errors = []
    
    for i, line in enumerate(lines):
        # Check each error pattern with context awareness
        for pattern in error_patterns:
            if has_error_context(line, pattern):
                errors.append({
                    'line': i + 1,
                    'text': line.strip()
                })
                break  # Only count this line once even if multiple patterns match
    
    if not errors:
        return None
    
    first_error = errors[0]
    error_count = len(errors)
    
    # Truncate error text to 100 chars
    error_text = first_error['text'][:100]
    if len(first_error['text']) > 100:
        error_text += "..."
    
    if error_count == 1:
        return f"{error_text} (line {first_error['line']})"
    else:
        return f"{error_text} (line {first_error['line']}) - {error_count} errors total"
