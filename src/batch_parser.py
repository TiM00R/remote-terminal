"""
Batch Script Execution - Output Parser
=======================================
Parse batch script output after execution completes.
Extracts step completion, errors, and summaries.
"""

import re
from typing import Optional


def count_step_markers(output: str) -> str:
    """
    Count [STEP_X_COMPLETE] markers in script output.
    
    Args:
        output: Complete script output
        
    Returns:
        String like "8/8" or "3/8" indicating completed/total steps
    """
    if not output:
        return "0/0"
    
    # Count completion markers
    completed = len(re.findall(r'\[STEP_\d+_COMPLETE\]', output))
    
    # Try to find total steps from headers like "=== [STEP 3/8] ==="
    total_match = re.search(r'\[STEP \d+/(\d+)\]', output)
    
    if total_match:
        total = int(total_match.group(1))
    else:
        # No total found, assume completed = total
        total = completed
    
    return f"{completed}/{total}"


def has_errors(output: str) -> bool:
    """
    Detect if output contains error indicators.
    
    Args:
        output: Script output to analyze
        
    Returns:
        True if errors detected, False otherwise
    """
    if not output:
        return False
    
    error_patterns = [
        r'ERROR:',
        r'FATAL:',
        r'\[CRITICAL_ERROR\]',
        r'\[ERROR\]',
        r'command not found',
        r'No such file or directory',
        r'Permission denied',
        r'Cannot',
        r'failed',
        r'Failed'
    ]
    
    return any(re.search(pattern, output, re.IGNORECASE) for pattern in error_patterns)


def extract_error_summary(output: str) -> Optional[str]:
    """
    Extract first error message from output.
    
    Args:
        output: Script output to analyze
        
    Returns:
        First error line (truncated to 200 chars) or None if no errors
    """
    if not output or not has_errors(output):
        return None
    
    lines = output.split('\n')
    
    # Look for lines containing error keywords
    error_keywords = ['ERROR', 'FATAL', 'FAILED', 'CRITICAL']
    
    for line in lines:
        line_upper = line.upper()
        if any(keyword in line_upper for keyword in error_keywords):
            # Return first 200 characters of error line
            return line.strip()[:200]
    
    return "Errors detected in output"


def check_completion_marker(output: str, marker: str = "[ALL_DIAGNOSTICS_COMPLETE]") -> bool:
    """
    Check if output contains completion marker.
    
    Args:
        output: Script output
        marker: Completion marker to look for
        
    Returns:
        True if marker found, False otherwise
    """
    return marker in output if output else False


def parse_script_output(output: str) -> dict:
    """
    Comprehensive parsing of script output.
    
    Args:
        output: Complete script output
        
    Returns:
        dict with parsing results:
        - steps_completed: "X/Y" format
        - error_detected: boolean
        - error_summary: string or None
        - all_complete: boolean (if [ALL_DIAGNOSTICS_COMPLETE] found)
        - total_lines: int
    """
    if not output:
        return {
            "steps_completed": "0/0",
            "error_detected": False,
            "error_summary": None,
            "all_complete": False,
            "total_lines": 0
        }
    
    return {
        "steps_completed": count_step_markers(output),
        "error_detected": has_errors(output),
        "error_summary": extract_error_summary(output),
        "all_complete": check_completion_marker(output),
        "total_lines": len(output.split('\n'))
    }
