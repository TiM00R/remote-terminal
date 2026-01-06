"""
SFTP Directory Download Operations

Smart directory download with automatic optimization and compression.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import os
import stat
import threading
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .tools_sftp_exceptions import (
    SFTPError,
    SFTPFileNotFoundError,
    SFTPConflictError
)
from .tools_sftp_utils import (
    format_file_size,
    validate_path,
    get_sftp_client,
    get_default_exclude_patterns
)
from .sftp_decisions import (
    analyze_file_list,
    make_transfer_decisions
)
from .sftp_progress import (
    TransferProgress,
    ProgressTracker
)
from .sftp_transfer_standard import (
    execute_standard_download,
    scan_remote_directory
)
from .sftp_transfer_compressed import (
    execute_compressed_download
)

logger = logging.getLogger(__name__)


async def sftp_download_directory(
    ssh_manager,
    remote_path: str,
    local_path: str,
    recursive: bool = True,
    if_exists: str = "merge",
    exclude_patterns: Optional[List[str]] = None,
    preserve_timestamps: bool = True,
    compression: str = "auto",
    background: Optional[bool] = None,
    shared_state = None
) -> Dict[str, Any]:
    """
    Smart directory download with automatic optimization.

    Similar to upload_directory but reversed direction.
    """

    start_time = datetime.now()

    # Validate paths
    validate_path(remote_path, "remote_path")
    validate_path(local_path, "local_path")

    # Validate if_exists parameter
    valid_policies = ["merge", "overwrite", "skip", "error"]
    if if_exists not in valid_policies:
        raise ValueError(f"if_exists must be one of {valid_policies}, got: {if_exists}")

    # Use default exclude patterns if not provided
    if exclude_patterns is None:
        exclude_patterns = get_default_exclude_patterns()
        logger.info(f"Using {len(exclude_patterns)} default exclude patterns")

    logger.info(f"Scanning remote directory: {remote_path}")

    # ===================================================================
    # STEP 1: SCAN REMOTE DIRECTORY (ONE SFTP OPERATION)
    # ===================================================================

    sftp = get_sftp_client(ssh_manager)

    try:
        remote_stat = sftp.stat(remote_path)
        if not stat.S_ISDIR(remote_stat.st_mode):
            raise SFTPError(f"Remote path is not a directory: {remote_path}")
    except FileNotFoundError:
        raise SFTPFileNotFoundError(f"Remote directory not found: {remote_path}")

    files = scan_remote_directory(sftp, remote_path, exclude_patterns)

    if not files:
        return {
            "status": "completed",
            "message": "No files to download (all excluded or empty directory)",
            "statistics": {"files_total": 0, "files_downloaded": 0}
        }

    # ===================================================================
    # STEP 2: ANALYZE AND MAKE DECISIONS
    # ===================================================================

    # Convert file list format for analysis
    files_for_analysis = [
        {'size': f['size'], 'local_path': f['remote_path']}
        for f in files
    ]

    analysis = analyze_file_list(files_for_analysis)

    decisions = make_transfer_decisions(
        file_count=analysis['total_count'],
        total_size=analysis['total_size'],
        text_ratio=None,  # Can't determine from remote
        compression_override=compression,
        background_override=background
    )

    logger.info(f"Transfer plan: {analysis['total_count']} files, "
                f"{format_file_size(analysis['total_size'])}, "
                f"compression={decisions['use_compression']}, "
                f"background={decisions['use_background']}, "
                f"estimated={decisions['estimated_time']:.1f}s")

    # Check if local directory exists
    local_exists = os.path.isdir(local_path)
    if local_exists and if_exists == "error":
        raise SFTPConflictError(f"Local directory exists and if_exists='error': {local_path}")

    # ===================================================================
    # STEP 3: CREATE TRANSFER TRACKING
    # ===================================================================

    transfer_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    progress = TransferProgress(
        transfer_id=transfer_id,
        transfer_type="download",
        source=remote_path,
        destination=local_path,
        method="compressed" if decisions['use_compression'] else "standard",
        status="starting",
        total_files=1 if decisions['use_compression'] else analysis['total_count'],
        total_bytes=analysis['total_size']
    )

    tracker = ProgressTracker(
        progress=progress,
        shared_state=shared_state,
        update_interval=0.5
    )

    if shared_state:
        shared_state.start_transfer(transfer_id, progress.to_dict())

    # ===================================================================
    # STEP 4: EXECUTE TRANSFER
    # ===================================================================

    if decisions['use_background']:
        # Start background thread
        thread = threading.Thread(
            target=_execute_download_background,
            args=(ssh_manager, remote_path, local_path, files, analysis['total_size'],
                  decisions['use_compression'], tracker, if_exists,
                  preserve_timestamps, exclude_patterns, shared_state),
            daemon=True
        )
        thread.start()

        # Return immediately
        return {
            "status": "started",
            "transfer_id": transfer_id,
            "method": "compressed" if decisions['use_compression'] else "standard",
            "total_files": analysis['total_count'],
            "total_size": analysis['total_size'],
            "estimated_time": decisions['estimated_time'],
            "message": f"Transfer started in background. Estimated time: {decisions['estimated_time']:.0f}s. View progress in web terminal."
        }
    else:
        # Execute blocking
        try:
            if decisions['use_compression']:
                result = execute_compressed_download(
                    ssh_manager=ssh_manager,
                    sftp=sftp,
                    files=files,
                    remote_root=remote_path,
                    local_root=local_path,
                    exclude_patterns=exclude_patterns,
                    tracker=tracker
                )
            else:
                result = execute_standard_download(
                    ssh_manager=ssh_manager,
                    sftp=sftp,
                    files=files,
                    remote_root=remote_path,
                    local_root=local_path,
                    if_exists=if_exists,
                    preserve_timestamps=preserve_timestamps,
                    tracker=tracker
                )

            # Mark complete
            tracker.complete()
            if shared_state:
                shared_state.complete_transfer(transfer_id, result)

            return result

        except Exception as e:
            logger.error(f"Download failed: {e}")
            tracker.complete(error=str(e))
            if shared_state:
                shared_state.complete_transfer(transfer_id, {
                    'status': 'error',
                    'error': str(e)
                })
            raise


def _execute_download_background(
    ssh_manager,
    remote_path: str,
    local_path: str,
    files: list,
    total_size: int,
    use_compression: bool,
    tracker: ProgressTracker,
    if_exists: str,
    preserve_timestamps: bool,
    exclude_patterns: list,
    shared_state
):
    """Background thread function for download"""
    try:
        sftp = ssh_manager.get_sftp()

        if use_compression:
            result = execute_compressed_download(
                ssh_manager=ssh_manager,
                sftp=sftp,
                files=files,
                remote_root=remote_path,
                local_root=local_path,
                exclude_patterns=exclude_patterns,
                tracker=tracker
            )
        else:
            result = execute_standard_download(
                ssh_manager=ssh_manager,
                sftp=sftp,
                files=files,
                remote_root=remote_path,
                local_root=local_path,
                if_exists=if_exists,
                preserve_timestamps=preserve_timestamps,
                tracker=tracker
            )

        tracker.complete()
        if shared_state:
            shared_state.complete_transfer(tracker.progress.transfer_id, result)

    except Exception as e:
        logger.error(f"Background download failed: {e}")
        tracker.complete(error=str(e))
        if shared_state:
            shared_state.complete_transfer(tracker.progress.transfer_id, {
                'status': 'error',
                'error': str(e)
            })
