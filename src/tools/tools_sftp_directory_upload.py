"""
SFTP Directory Upload Operations

Smart directory upload with automatic optimization and compression.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import os
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
    execute_standard_upload,
    scan_local_directory
)
from .sftp_transfer_compressed import (
    execute_compressed_upload
)

logger = logging.getLogger(__name__)


async def sftp_upload_directory(
    ssh_manager,
    local_path: str,
    remote_path: str,
    recursive: bool = True,
    if_exists: str = "merge",
    exclude_patterns: Optional[List[str]] = None,
    chmod_files: Optional[int] = None,
    chmod_dirs: Optional[int] = None,
    preserve_timestamps: bool = True,
    compression: str = "auto",
    background: Optional[bool] = None,
    shared_state = None
) -> Dict[str, Any]:
    """
    Smart directory upload with automatic optimization.

    Automatically decides:
    - Whether to use compression (based on file count and types)
    - Whether to run in background (based on estimated time)

    For quick transfers (<10s): Blocks and returns result
    For large transfers (>10s): Starts background thread, returns immediately

    Args:
        ssh_manager: SSH manager instance
        local_path: Absolute path to local directory
        remote_path: Absolute path on remote server
        recursive: Include subdirectories (default: True)
        if_exists: Conflict policy: "merge", "overwrite", "skip", "error"
        exclude_patterns: List of glob patterns to exclude (None = use defaults)
        chmod_files: Optional file permissions (e.g., 420 for 0o644)
        chmod_dirs: Optional directory permissions (e.g., 493 for 0o755)
        preserve_timestamps: Copy local mtimes to remote files
        compression: "auto", "always", or "never"
        background: None = auto-decide, True = force background, False = force blocking
        shared_state: Shared state instance for progress tracking

    Returns:
        Dict with transfer results (immediate for blocking, transfer_id for background)
    """

    start_time = datetime.now()

    # Validate paths
    validate_path(local_path, "local_path")
    validate_path(remote_path, "remote_path")

    if not os.path.isdir(local_path):
        raise SFTPFileNotFoundError(f"Local directory not found: {local_path}")

    # Validate if_exists parameter
    valid_policies = ["merge", "overwrite", "skip", "error"]
    if if_exists not in valid_policies:
        raise ValueError(f"if_exists must be one of {valid_policies}, got: {if_exists}")

    # Use default exclude patterns if not provided
    if exclude_patterns is None:
        exclude_patterns = get_default_exclude_patterns()
        logger.info(f"Using {len(exclude_patterns)} default exclude patterns")

    logger.info(f"Scanning local directory: {local_path}")

    # ===================================================================
    # STEP 1: SCAN LOCAL DIRECTORY (NO REMOTE COMMANDS!)
    # ===================================================================

    files = scan_local_directory(local_path, exclude_patterns)

    if not files:
        return {
            "status": "completed",
            "message": "No files to upload (all excluded or empty directory)",
            "statistics": {"files_total": 0, "files_uploaded": 0}
        }

    # ===================================================================
    # STEP 2: ANALYZE AND MAKE DECISIONS (NO REMOTE COMMANDS!)
    # ===================================================================

    analysis = analyze_file_list(files)

    decisions = make_transfer_decisions(
        file_count=analysis['total_count'],
        total_size=analysis['total_size'],
        text_ratio=analysis['text_ratio'],
        compression_override=compression,
        background_override=background
    )

    logger.info(f"Transfer plan: {analysis['total_count']} files, "
                f"{format_file_size(analysis['total_size'])}, "
                f"compression={decisions['use_compression']}, "
                f"background={decisions['use_background']}, "
                f"estimated={decisions['estimated_time']:.1f}s")

    # ===================================================================
    # STEP 3: CREATE TRANSFER TRACKING
    # ===================================================================

    transfer_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    progress = TransferProgress(
        transfer_id=transfer_id,
        transfer_type="upload",
        source=local_path,
        destination=remote_path,
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
            target=_execute_upload_background,
            args=(ssh_manager, local_path, remote_path, files, analysis['total_size'],
                  decisions['use_compression'], tracker, if_exists,
                  chmod_files, chmod_dirs, preserve_timestamps,
                  exclude_patterns, shared_state),
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
            sftp = get_sftp_client(ssh_manager)

            if decisions['use_compression']:
                result = execute_compressed_upload(
                    ssh_manager=ssh_manager,
                    sftp=sftp,
                    files=files,
                    local_root=local_path,
                    remote_root=remote_path,
                    exclude_patterns=exclude_patterns,
                    chmod_dirs=chmod_dirs,
                    tracker=tracker
                )
            else:
                result = execute_standard_upload(
                    ssh_manager=ssh_manager,
                    sftp=sftp,
                    files=files,
                    local_root=local_path,
                    remote_root=remote_path,
                    if_exists=if_exists,
                    chmod_files=chmod_files,
                    chmod_dirs=chmod_dirs,
                    preserve_timestamps=preserve_timestamps,
                    tracker=tracker
                )

            # Mark complete
            tracker.complete()
            if shared_state:
                shared_state.complete_transfer(transfer_id, result)

            return result

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            tracker.complete(error=str(e))
            if shared_state:
                shared_state.complete_transfer(transfer_id, {
                    'status': 'error',
                    'error': str(e)
                })
            raise


def _execute_upload_background(
    ssh_manager,
    local_path: str,
    remote_path: str,
    files: list,
    total_size: int,
    use_compression: bool,
    tracker: ProgressTracker,
    if_exists: str,
    chmod_files: Optional[int],
    chmod_dirs: Optional[int],
    preserve_timestamps: bool,
    exclude_patterns: list,
    shared_state
):
    """Background thread function for upload"""
    try:
        sftp = ssh_manager.get_sftp()

        if use_compression:
            result = execute_compressed_upload(
                ssh_manager=ssh_manager,
                sftp=sftp,
                files=files,
                local_root=local_path,
                remote_root=remote_path,
                exclude_patterns=exclude_patterns,
                chmod_dirs=chmod_dirs,
                tracker=tracker
            )
        else:
            result = execute_standard_upload(
                ssh_manager=ssh_manager,
                sftp=sftp,
                files=files,
                local_root=local_path,
                remote_root=remote_path,
                if_exists=if_exists,
                chmod_files=chmod_files,
                chmod_dirs=chmod_dirs,
                preserve_timestamps=preserve_timestamps,
                tracker=tracker
            )

        tracker.complete()
        if shared_state:
            shared_state.complete_transfer(tracker.progress.transfer_id, result)

    except Exception as e:
        logger.error(f"Background upload failed: {e}")
        tracker.complete(error=str(e))
        if shared_state:
            shared_state.complete_transfer(tracker.progress.transfer_id, {
                'status': 'error',
                'error': str(e)
            })
