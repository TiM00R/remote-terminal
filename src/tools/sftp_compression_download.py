"""
Compressed Download Workflow
Complete workflow for downloading and extracting directories
"""

import os
import tarfile
import tempfile
import time
import logging
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)


def download_and_extract(
    ssh_manager,
    sftp,
    remote_dir: str,
    local_dir: str,
    exclude_patterns: List[str] = None,
    tracker=None
) -> dict:
    """
    Complete compressed download workflow:
    1. Create tar.gz on remote
    2. Download via SFTP
    3. Extract locally
    4. Cleanup temporary files

    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        remote_dir: Remote directory to download
        local_dir: Local destination directory
        exclude_patterns: Patterns to exclude
        tracker: Optional progress tracker

    Returns:
        Dict with complete transfer statistics
    """

    start_time = datetime.now()

    # Generate unique temp filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    remote_archive = f"/tmp/download_{timestamp}.tar.gz"
    local_archive = tempfile.mktemp(suffix=f'_download_{timestamp}.tar.gz')

    try:
        # Step 1: Create tarball on remote
        logger.info("Step 1/4: Creating tarball on remote...")
        if tracker:
            tracker.update(phase="compressing", status="in_progress")

        # Build tar command with exclusions
        exclude_args = ""
        if exclude_patterns:
            for pattern in exclude_patterns:
                exclude_args += f" --exclude='{pattern}'"

        tar_cmd = f"tar -czf {remote_archive}{exclude_args} -C {remote_dir} ."

        compress_start = datetime.now()
        result = ssh_manager.execute_command(tar_cmd, timeout=600)
        compress_duration = (datetime.now() - compress_start).total_seconds()

        if result.exit_code != 0:
            raise Exception(f"Remote tar creation failed: {result.stderr}")

        # Get archive size
        stat_result = ssh_manager.execute_command(f"stat -c %s {remote_archive}", timeout=10)
        compressed_size = int(stat_result.stdout.strip()) if stat_result.stdout.strip().isdigit() else 0

        logger.info(f"Remote tarball created in {compress_duration:.1f}s ({compressed_size/(1024*1024):.1f}MB)")

        # Compression complete - DON'T update transferred_bytes (stays at 0%)
        # Phase display will show "Compressing..." with 0%

        # Step 2: Download tarball
        logger.info("Step 2/4: Downloading tarball...")
        if tracker:
            # FIX: Reset completed_files to 0 when switching to transfer phase
            # Now we're transferring 1 file (the archive)
            tracker.update(
                phase="transferring",
                status="in_progress",
                transferred_bytes=0,
                completed_files=0
            )

        download_start = datetime.now()

        # Use SFTP with progress callback
        def download_callback(bytes_transferred, total_bytes):
            if tracker and bytes_transferred > 0:
                # NOW we update percentage - actual file transfer
                tracker.update(
                    phase="transferring",
                    status="in_progress",
                    transferred_bytes=bytes_transferred,
                    completed_files=0,
                    current_file=os.path.basename(remote_archive)
                )

        sftp.get(remote_archive, local_archive, callback=download_callback)
        download_duration = (datetime.now() - download_start).total_seconds()

        logger.info(f"Download completed in {download_duration:.1f}s "
                   f"({compressed_size/(1024*1024)/download_duration:.1f} MB/s)")

        # Transfer complete - set to 100%
        if tracker:
            tracker.update(
                phase="transferring",
                status="in_progress",
                transferred_bytes=tracker.progress.total_bytes,
                completed_files=1
            )

        # Step 3: Extract locally
        logger.info("Step 3/4: Extracting locally...")
        if tracker:
            tracker.update(phase="extracting", status="in_progress")

        os.makedirs(local_dir, exist_ok=True)

        extract_start = datetime.now()
        with tarfile.open(local_archive, 'r:gz') as tar:
            tar.extractall(local_dir)
        extract_duration = (datetime.now() - extract_start).total_seconds()

        logger.info(f"Extraction completed in {extract_duration:.1f}s")
        if tracker:
            time.sleep(1.0)  # 1 second delay

        # Extraction phase - DON'T change transferred_bytes (stays at 100% from transfer)
        # Phase display will show "Extracting..." with 100%

        # Step 4: Cleanup
        logger.info("Step 4/4: Cleaning up...")

        # Remove local archive
        if os.path.exists(local_archive):
            os.remove(local_archive)

        # Remove remote archive
        ssh_manager.execute_command(f"rm {remote_archive}", timeout=30)

        total_duration = (datetime.now() - start_time).total_seconds()

        # Final update: completed
        if tracker:
            tracker.update(
                phase="completed",
                status="completed",
                transferred_bytes=tracker.progress.total_bytes,
                completed_files=1
            )

        return {
            'status': 'success',
            'method': 'compressed',
            'compressed_size': compressed_size,
            'compression_duration': compress_duration,
            'download_duration': download_duration,
            'extraction_duration': extract_duration,
            'total_duration': total_duration,
            'error': None
        }

    except Exception as e:
        logger.error(f"Compressed download failed: {e}")

        # Cleanup on error
        if os.path.exists(local_archive):
            os.remove(local_archive)

        try:
            ssh_manager.execute_command(f"rm -f {remote_archive}", timeout=10)
        except:
            pass

        return {
            'status': 'error',
            'method': 'compressed',
            'error': str(e)
        }
