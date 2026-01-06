"""
Formatting Utility Functions
Duration, bytes, paths, and timestamps
"""

import time
from datetime import datetime
from pathlib import Path


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "45.2s", "2m 15s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_bytes(bytes_count: int) -> str:
    """
    Format byte count in human-readable format

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 KB", "2.3 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def expand_path(path: str) -> Path:
    """
    Expand user home directory and resolve path

    Args:
        path: Path string (may contain ~)

    Returns:
        Resolved Path object
    """
    return Path(path).expanduser().resolve()


def timestamp_now() -> str:
    """
    Get current timestamp in ISO format

    Returns:
        ISO formatted timestamp string
    """
    return datetime.utcnow().isoformat()


def timestamp_local() -> str:
    """
    Get current local timestamp

    Returns:
        Formatted local timestamp
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_command_prompt(user: str, host: str, path: str = "~") -> str:
    """
    Format command prompt string

    Args:
        user: Username
        host: Hostname
        path: Current path

    Returns:
        Formatted prompt
    """
    return f"{user}@{host}:{path}$ "


class Timer:
    """Simple timer context manager"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

    def elapsed(self) -> float:
        """Get elapsed time"""
        if self.duration is not None:
            return self.duration
        elif self.start_time is not None:
            return time.time() - self.start_time
        return 0.0
