"""
Batch Script Execution - Helper Utilities
==========================================
Utility functions for batch script execution.
No business logic - just helpers.
"""

from datetime import datetime
import os
from pathlib import Path


def generate_script_paths(timestamp_str: str = None, local_log_dir: str = None) -> dict:
    """
    Generate unique file paths for batch script execution.
    
    Args:
        timestamp_str: Human-readable timestamp like "20251115_233630" (uses current time if None)
        local_log_dir: Local directory for logs (uses default if None)
        
    Returns:
        dict with remote_script, remote_log, local_log paths
        
    Example:
        paths = generate_script_paths()
        # Returns: {
        #     "timestamp": "20251120_043530",
        #     "remote_script": "/tmp/batch_script_20251120_043530.sh",
        #     "remote_log": "/tmp/batch_output_20251120_043530.log",
        #     "local_log": "/home/user/mcp_batch_logs/batch_output_20251120_043530.log"
        # }
    """
    if timestamp_str is None:
        # Format: YYYYMMDD_HHMMSS (e.g., 20251120_043530)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Use provided directory or default to user's home
    if local_log_dir is None:
        # Platform-independent home directory
        home = Path.home()
        local_log_dir = home / "mcp_batch_logs"
    else:
        local_log_dir = Path(local_log_dir)
    
    return {
        "timestamp": timestamp_str,
        "remote_script": f"/tmp/batch_script_{timestamp_str}.sh",
        "remote_log": f"/tmp/batch_output_{timestamp_str}.log",
        "local_log": str(local_log_dir / f"batch_output_{timestamp_str}.log")
    }


def ensure_local_log_directory(local_log_path: str) -> None:
    """
    Ensure local log directory exists.
    
    Args:
        local_log_path: Full path to local log file
    """
    log_dir = os.path.dirname(local_log_path)
    Path(log_dir).mkdir(parents=True, exist_ok=True)


def get_first_lines(text: str, n: int) -> str:
    """
    Get first N lines from text.
    
    Args:
        text: Input text
        n: Number of lines
        
    Returns:
        First N lines joined with newlines
    """
    if not text:
        return ""
    lines = text.split('\n')
    return '\n'.join(lines[:n])


def get_last_lines(text: str, n: int) -> str:
    """
    Get last N lines from text.
    
    Args:
        text: Input text
        n: Number of lines
        
    Returns:
        Last N lines joined with newlines
    """
    if not text:
        return ""
    lines = text.split('\n')
    return '\n'.join(lines[-n:]) if len(lines) > n else text


def format_execution_time(seconds: float) -> str:
    """
    Format execution time for human readability.
    
    Args:
        seconds: Execution time in seconds
        
    Returns:
        Formatted string like "2.3s" or "1m 23s"
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}m {remaining_seconds}s"
