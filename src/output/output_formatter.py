"""
Output formatting utilities for MCP server
Handles filtering and formatting command output for Claude
"""

import logging
from typing import Dict
from error_check_helper import check_for_errors

logger = logging.getLogger(__name__)


# ============================================================================
# SMART OUTPUT FORMATTING HELPERS
# ============================================================================

# Obsolete helper. Will be removed in future. Or integrated into format_output().
def find_errors_with_context(
    output: str,
    error_patterns: list,
    max_errors: int = 10
) -> list:
    """
    Find errors with surrounding context (line before + error + line after)
    """
    lines = output.split('\n')
    errors = []
    
    for i, line in enumerate(lines):
        if len(errors) >= max_errors:
            break
        
        if any(pattern.lower() in line.lower() for pattern in error_patterns):
            errors.append({
                "line_number": i + 1,
                "before": lines[i-1] if i > 0 else "",
                "error": line,
                "after": lines[i+1] if i < len(lines)-1 else ""
            })
    
    return errors


# NOTE: check_for_errors() is now imported from error_check_helper.py
# This avoids code duplication and uses the improved context-aware version


def format_output(
    command: str,
    output: str,
    status: str,
    output_mode: str,
    config,
    output_filter=None
) -> dict:
    """Format output based on mode for token efficiency"""
    lines = output.split('\n')
    line_count = len(lines)
    size_kb = len(output) / 1024
    
    buffer_info = {
        "total_lines": line_count,
        "buffer_size_kb": round(size_kb, 2)
    }
    
    # ALWAYS check for errors in full output (before any filtering)
    error_summary = check_for_errors(output, config.claude.error_patterns)
    
    # RAW MODE - return completely unfiltered output
    if output_mode == "raw":
        return {
            "error": error_summary,
            "buffer_info": buffer_info,
            "raw_output": output,
            "output_mode": "raw"
        }
    
    # Apply smart filtering to output (command-aware truncation)
    if output_filter:
        filtered_output = output_filter.filter_output(command, output)
    else:
        # No filter provided, use raw output
        filtered_output = output
    
    # Now apply output_mode to the filtered output
    if output_mode == "minimal":
        return {
            "error": error_summary,
            "buffer_info": buffer_info,
            "output_mode": "minimal"
        }
    
    elif output_mode == "summary":
        has_errors = error_summary is not None
        return {
            "error": error_summary,
            "buffer_info": buffer_info,
            "has_errors": has_errors,
            "output_mode": "summary",
            "message": f"{line_count} lines" + (" - ERRORS DETECTED" if has_errors else "")
        }
    
    elif output_mode == "preview":
        # Preview of the FILTERED output
        filtered_lines = filtered_output.split('\n')
        head = config.claude.output_modes.preview_head_lines
        tail = config.claude.output_modes.preview_tail_lines
        
        if len(filtered_lines) <= head + tail:
            # Filtered output is small enough, return it all
            preview_output = filtered_output
        else:
            # Extract head + tail from filtered output
            first_lines = '\n'.join(filtered_lines[:head])
            last_lines = '\n'.join(filtered_lines[-tail:])
            preview_output = first_lines + '\n\n[... lines omitted ...]\n\n' + last_lines
        
        return {
            "error": error_summary,
            "buffer_info": buffer_info,
            "output_preview": {
                "first_lines": first_lines,
                "last_lines": last_lines
            },
            "output_mode": "preview",            
            "full_output_available": True,
            "message": f"Preview of filtered output ({line_count} original lines)"
        }
    
    elif output_mode == "full":
        # Return complete filtered output
        return {
            "error": error_summary,
            "buffer_info": buffer_info,
            "output": filtered_output,
            "output_mode": "full"
        }
    
    elif output_mode == "auto":
        # Smart decision based on output size
        threshold = config.claude.output_modes.full_output_threshold
        
        if line_count < threshold:
            # Small output - return full filtered
            return {
                "error": error_summary,
                "buffer_info": buffer_info,
                "output": filtered_output,
                "output_mode": "full"
            }
        else:
            # Large output - return preview of filtered
            filtered_lines = filtered_output.split('\n')
            head = config.claude.output_modes.preview_head_lines
            tail = config.claude.output_modes.preview_tail_lines
            
            if len(filtered_lines) <= head + tail:
                preview_output = filtered_output
            else:
                first_lines = '\n'.join(filtered_lines[:head])
                last_lines = '\n'.join(filtered_lines[-tail:])
                preview_output = first_lines + '\n\n[... lines omitted ...]\n\n' + last_lines
            
            return {
                "error": error_summary,
                "buffer_info": buffer_info,
                "output_preview": {
                    "first_lines": first_lines,
                    "last_lines": last_lines
                },
                "output_mode": "preview",
                "full_output_available": True,
                "message": f"Large output ({line_count} lines). Use get_command_output() for full."
            }
    
    # Fallback - should never reach here
    return {
        "error": error_summary,
        "buffer_info": buffer_info,
        "output": filtered_output
    }
