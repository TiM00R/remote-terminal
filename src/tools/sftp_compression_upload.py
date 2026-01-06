"""
Compressed Upload Workflow
Complete workflow for compressing and uploading directories
"""

import os
import tempfile
import time
import logging
from typing import List, Optional
from datetime import datetime
from tools.sftp_compression_tar import create_tarball, extract_tarball_via_ssh

logger = logging.getLogger(__name__)


def compress_and_upload(
    ssh_manager,
    sftp,
    local_dir: str,
    remote_dir: str,
    exclude_patterns: List[str] = None,
    chmod_dirs: Optional[int] = None,
    tracker=None
) -> dict:
    """
    Complete compressed upload workflow:
    1. Create local tar.gz
    2. Upload via SFTP
    3. Extract on remote
    4. Cleanup temporary files

    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        local_dir: Local directory to upload
        remote_dir: Remote destination directory
        exclude_patterns: Patterns to exclude
        chmod_dirs: Optional permissions for directories
        tracker: Optional progress tracker

    Returns:
        Dict with complete transfer statistics
    """

    start_time = datetime.now()

    # Generate unique temp filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    local_archive = tempfile.mktemp(suffix=f'_upload_{timestamp}.tar.gz')
    remote_archive = f"/tmp/upload_{timestamp}.tar.gz"

    try:
        # Step 1: Create tarball
        logger.info("Step 1/4: Creating local tarball...")
        if tracker:
            tracker.update(phase="compressing", status="in_progress")

        tar_info = create_tarball(local_dir, local_archive, exclude_patterns, tracker=tracker)

        # Compression complete - DON'T update transferred_bytes (stays at 0%)
        # Phase display will show "Compressing..." with 0%

        # Step 2: Upload tarball
        logger.info("Step 2/4: Uploading tarball...")
        if tracker:
            # FIX: Reset completed_files to 0 when switching to transfer phase
            # Now we're transferring 1 file (the archive), not the original file count
            tracker.update(
                phase="transferring",
                status="in_progress",
                transferred_bytes=0,
                completed_files=0
            )

        upload_start = datetime.now()

        # Use SFTP with progress callback

        def upload_callback(bytes_transferred, total_bytes):
            if tracker and bytes_transferred > 0:
                # NOW we update percentage - actual file transfer
                tracker.update(
                    phase="transferring",
                    status="in_progress",
                    transferred_bytes=bytes_transferred,
                    completed_files=0,
                    current_file=os.path.basename(remote_archive)
                )

        sftp.put(local_archive, remote_archive, callback=upload_callback)
        upload_duration = (datetime.now() - upload_start).total_seconds()

        logger.info(f"Upload completed in {upload_duration:.1f}s "
                   f"({tar_info['compressed_size']/(1024*1024)/upload_duration:.1f} MB/s)")

        # Transfer complete - set to 100%
        if tracker:
            tracker.update(
                phase="transferring",
                status="in_progress",
                transferred_bytes=tracker.progress.total_bytes,
                completed_files=1
            )

        # Step 3: Extract on remote
        logger.info("Step 3/4: Extracting on remote...")
        extract_info = extract_tarball_via_ssh(
            ssh_manager, remote_archive, remote_dir,
            cleanup_archive=False,
            tracker=tracker
        )

        if extract_info['status'] != 'success':
            raise Exception(f"Extraction failed: {extract_info['error']}")


        # Extraction phase - DON'T change transferred_bytes (stays at 100% from transfer)
        # Phase display will show "Extracting..." with 100%
        # ✅ ADD THIS - Give web terminal time to poll and display extraction phase

        if tracker:
            time.sleep(1.0)  # 1 second delay to ensure extraction phase is visible

        # Step 4: Set permissions on remote directory if requested
        if chmod_dirs is not None:
            logger.info("Step 4/4: Setting directory permissions...")
            chmod_cmd = f"chmod -R {oct(chmod_dirs)[2:]} {remote_dir}"
            ssh_manager.execute_command(chmod_cmd, timeout=60)

        # Cleanup local archive
        if os.path.exists(local_archive):
            os.remove(local_archive)
            logger.info(f"Cleaned up local archive: {local_archive}")

        total_duration = (datetime.now() - start_time).total_seconds()
        #  CRITICAL: Set status="completed" BEFORE cleanup
        if tracker:
            tracker.update(
                phase="completed",
                status="completed",
                transferred_bytes=tracker.progress.total_bytes,
                completed_files=1
            )

        #  NOW run cleanup AFTER progress is completed
        cleanup_cmd = f"rm -f {remote_archive}"
        ssh_manager.execute_command(cleanup_cmd, timeout=30)
        logger.info(f"Cleaned up remote archive: {remote_archive}")


        return {
            'status': 'success',
            'method': 'compressed',
            'uncompressed_size': tar_info['uncompressed_size'],
            'compressed_size': tar_info['compressed_size'],
            'compression_ratio': tar_info['compression_ratio'],
            'file_count': tar_info['file_count'],
            'compression_duration': tar_info['duration'],
            'upload_duration': upload_duration,
            'extraction_duration': extract_info['duration'],
            'total_duration': total_duration,
            'error': None
        }

    except Exception as e:
        logger.error(f"Compressed upload failed: {e}")

        # Cleanup on error
        if os.path.exists(local_archive):
            os.remove(local_archive)

        # Try to cleanup remote archive
        try:
            ssh_manager.execute_command(f"rm -f {remote_archive}", timeout=10)
        except:
            pass

        return {
            'status': 'error',
            'method': 'compressed',
            'error': str(e)
        }
