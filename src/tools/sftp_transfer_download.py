"""
SFTP Standard Download Operations

Standard file-by-file download for directories.
Used when compression is not beneficial.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.2 - FIXED: Set status to "completed" when transfer finishes
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def execute_standard_download(
    ssh_manager,
    sftp,
    files: List[Dict],
    remote_root: str,
    local_root: str,
    if_exists: str,
    preserve_timestamps: bool,
    tracker
) -> Dict[str, Any]:
    """
    Execute standard file-by-file download.

    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        files: List of file dicts with 'remote_path', 'rel_path', 'size', 'attr'
        remote_root: Remote root directory
        local_root: Local root directory
        if_exists: Conflict resolution policy
        preserve_timestamps: Whether to preserve timestamps
        tracker: Progress tracker instance

    Returns:
        Dict with transfer statistics
    """

    start_time = datetime.now()

    stats = {
        'files_downloaded': 0,
        'files_skipped': 0,
        'files_overwritten': 0,
        'dirs_created': 0,
        'bytes_transferred': 0
    }

    skipped_files = []

    # Ensure local root exists
    os.makedirs(local_root, exist_ok=True)

    # FIX: Set phase to transferring for standard transfers
    tracker.update(phase="transferring", status="in_progress")

    # Transfer each file
    for idx, file_info in enumerate(files):
        remote_path = file_info['remote_path']
        rel_path = file_info['rel_path']
        file_size = file_info['size']
        attr = file_info['attr']

        local_path = os.path.join(local_root, rel_path)

        try:
            # Create local parent directories if needed
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
                stats['dirs_created'] += 1

            # Check if local file exists
            file_exists = os.path.isfile(local_path)

            # Apply if_exists policy
            should_download = True
            if file_exists:
                if if_exists == "skip":
                    should_download = False
                    stats['files_skipped'] += 1
                    skipped_files.append(rel_path)
                    logger.debug(f"Skipped existing file: {local_path}")
                elif if_exists == "overwrite" or if_exists == "merge":
                    stats['files_overwritten'] += 1

            # Download file
            if should_download:
                # Create progress callback for this file
                bytes_before_transfer = stats['bytes_transferred']

                def file_callback(transferred, total):
                    tracker.update(
                        current_file=rel_path,
                        completed_files=idx,
                        transferred_bytes=bytes_before_transfer + transferred,
                        phase="transferring",
                        status="in_progress"
                    )

                # Download with progress callback
                sftp.get(remote_path, local_path, callback=file_callback)

                # Preserve timestamp if requested
                if preserve_timestamps:
                    os.utime(local_path, (attr.st_atime, attr.st_mtime))

                stats['files_downloaded'] += 1
                stats['bytes_transferred'] += file_size

                logger.debug(f"Downloaded: {rel_path} ({file_size} bytes)")

        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            tracker.add_error(rel_path, str(e))

    duration = (datetime.now() - start_time).total_seconds()

    # FIX: Mark transfer as completed
    tracker.update(
        phase="completed",
        status="completed",
        completed_files=len(files),
        transferred_bytes=stats['bytes_transferred']
    )

    return {
        'status': 'success',
        'method': 'standard',
        'statistics': stats,
        'skipped_files': skipped_files[:20],  # Limit to first 20
        'skipped_count': len(skipped_files),
        'duration': duration
    }
