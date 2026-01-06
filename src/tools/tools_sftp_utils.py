"""
SFTP Utility Functions

Helper functions for SFTP operations including formatting, validation, and client access.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import os
import logging
from typing import List
from datetime import datetime
import paramiko

from .tools_sftp_exceptions import SFTPConnectionError

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Phase 1 - Keep as is)
# ============================================================================

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_permissions(mode: int) -> str:
    """Convert numeric permissions to octal string format."""
    return f"0{mode & 0o777:o}"


def timestamp_to_iso(timestamp: float) -> str:
    """Convert Unix timestamp to ISO format string."""
    return datetime.fromtimestamp(timestamp).isoformat() + 'Z'


def validate_path(path: str, path_type: str = "path") -> None:
    """
    Validate a file path for security issues.

    Args:
        path: Path to validate
        path_type: Type of path (for error messages)

    Raises:
        ValueError: If path contains security issues
    """
    if not path:
        raise ValueError(f"{path_type} cannot be empty")

    # Normalize path
    normalized = os.path.normpath(path)

    # Check for path traversal attempts
    if '..' in normalized:
        raise ValueError(f"Path traversal detected in {path_type}: {path}")


def get_sftp_client(ssh_manager) -> paramiko.SFTPClient:
    """
    Get SFTP client from SSH manager.

    Args:
        ssh_manager: SSH manager instance

    Returns:
        SFTP client

    Raises:
        SFTPConnectionError: If SFTP connection not available
    """
    if not ssh_manager.is_connected():
        raise SFTPConnectionError("SSH not connected. Use select_server first.")

    try:
        return ssh_manager.get_sftp()
    except Exception as e:
        logger.error(f"Failed to get SFTP client: {e}")
        raise SFTPConnectionError(f"Failed to establish SFTP connection: {e}")


def get_default_exclude_patterns() -> List[str]:
    """Get default exclude patterns for common unwanted files/directories."""
    return [
        '.git',
        '.git/**',
        '__pycache__',
        '__pycache__/**',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.Python',
        'node_modules',
        'node_modules/**',
        '.venv',
        '.venv/**',
        'venv',
        'venv/**',
        '.env',
        '.DS_Store',
        'Thumbs.db',
        '*.swp',
        '*.swo',
        '*~',
        '.idea',
        '.idea/**',
        '.vscode',
        '.vscode/**',
        '*.log'
    ]
