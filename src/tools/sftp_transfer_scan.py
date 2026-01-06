"""
SFTP Directory Scanning Operations

Scans local and remote directories for file transfer operations.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.0
"""

import os
import stat
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def scan_local_directory(
    local_path: str,
    exclude_patterns: List[str]
) -> List[Dict[str, Any]]:
    """
    Scan local directory and collect file information.

    Args:
        local_path: Local directory to scan
        exclude_patterns: List of exclusion patterns

    Returns:
        List of file dicts with 'local_path', 'rel_path', 'size'
    """

    files = []

    # Helper to check exclusions
    def should_exclude(rel_path, filename):
        if not exclude_patterns:
            return False

        import fnmatch
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    # Walk directory tree
    for root, dirs, filenames in os.walk(local_path):
        # Filter excluded directories
        dirs[:] = [d for d in dirs if not should_exclude(
            os.path.relpath(os.path.join(root, d), local_path), d
        )]

        for filename in filenames:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, local_path)

            # Skip excluded files
            if should_exclude(rel_path, filename):
                logger.debug(f"Excluded: {rel_path}")
                continue

            try:
                size = os.path.getsize(filepath)
                files.append({
                    'local_path': filepath,
                    'rel_path': rel_path,
                    'size': size
                })
            except Exception as e:
                logger.warning(f"Error scanning {filepath}: {e}")

    return files


def scan_remote_directory(
    sftp,
    remote_path: str,
    exclude_patterns: List[str]
) -> List[Dict[str, Any]]:
    """
    Scan remote directory and collect file information.

    Args:
        sftp: SFTP client
        remote_path: Remote directory to scan
        exclude_patterns: List of exclusion patterns

    Returns:
        List of file dicts with 'remote_path', 'rel_path', 'size', 'attr'
    """

    files = []

    # Helper to check exclusions
    def should_exclude(rel_path, filename):
        if not exclude_patterns:
            return False

        import fnmatch
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    # Recursive scan function
    def scan_dir(path):
        try:
            for attr in sftp.listdir_attr(path):
                item_name = attr.filename
                full_path = f"{path}/{item_name}".replace('//', '/')
                rel_path = os.path.relpath(full_path, remote_path)

                # Skip excluded items
                if should_exclude(rel_path, item_name):
                    logger.debug(f"Excluded: {rel_path}")
                    continue

                # Handle directories
                if stat.S_ISDIR(attr.st_mode):
                    scan_dir(full_path)

                # Handle files
                elif stat.S_ISREG(attr.st_mode):
                    files.append({
                        'remote_path': full_path,
                        'rel_path': rel_path,
                        'size': attr.st_size,
                        'attr': attr
                    })

        except Exception as e:
            logger.error(f"Error scanning remote directory {path}: {e}")

    scan_dir(remote_path)

    return files
