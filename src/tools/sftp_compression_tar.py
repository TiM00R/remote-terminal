"""
Tarball Creation and Extraction
Core tar.gz compression and extraction operations
"""

import os
import tarfile
import logging
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)


def create_tarball(
    source_dir: str,
    output_path: str,
    exclude_patterns: List[str] = None,
    compression_level: int = 6,
    tracker=None
) -> dict:
    """
    Create a tar.gz archive from a directory.

    Args:
        source_dir: Directory to compress
        output_path: Path for output .tar.gz file
        exclude_patterns: List of patterns to exclude (applied during creation)
        compression_level: Compression level 1-9 (6 is default, good balance)
        tracker: Optional progress tracker

    Returns:
        Dict with:
        - archive_path: Path to created archive
        - uncompressed_size: Original size in bytes
        - compressed_size: Archive size in bytes
        - compression_ratio: Ratio (0.0 to 1.0)
        - file_count: Number of files included
        - duration: Time taken in seconds
    """

    start_time = datetime.now()

    logger.info(f"Creating tarball from {source_dir}")

    # Track statistics
    uncompressed_size = 0
    file_count = 0

    # Helper to check exclusions
    def should_exclude(filepath):
        if not exclude_patterns:
            return False

        rel_path = os.path.relpath(filepath, source_dir)
        filename = os.path.basename(filepath)

        import fnmatch
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

    try:
        # Create tar.gz with specified compression level
        with tarfile.open(output_path, f'w:gz', compresslevel=compression_level) as tar:

            # Walk directory and add files
            for root, dirs, files in os.walk(source_dir):
                # Filter excluded directories
                dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d))]

                for filename in files:
                    filepath = os.path.join(root, filename)

                    # Skip excluded files
                    if should_exclude(filepath):
                        logger.debug(f"Excluding from tarball: {filepath}")
                        continue

                    try:
                        # Get file size before compression
                        file_size = os.path.getsize(filepath)
                        uncompressed_size += file_size
                        file_count += 1

                        # Add to archive with relative path
                        arcname = os.path.relpath(filepath, source_dir)
                        tar.add(filepath, arcname=arcname)

                        logger.debug(f"Added to tarball: {arcname} ({file_size} bytes)")

                        # Update progress every 10 files
                        if tracker and file_count % 10 == 0:
                            tracker.update(
                                phase="compressing",
                                status="in_progress",
                                current_file=arcname
                            )

                    except Exception as e:
                        logger.warning(f"Failed to add {filepath} to tarball: {e}")

        # Get compressed size
        compressed_size = os.path.getsize(output_path)
        compression_ratio = compressed_size / uncompressed_size if uncompressed_size > 0 else 0

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Tarball created: {file_count} files, "
                   f"{uncompressed_size/(1024*1024):.1f}MB -> {compressed_size/(1024*1024):.1f}MB "
                   f"({compression_ratio:.1%} ratio) in {duration:.1f}s")

        return {
            'archive_path': output_path,
            'uncompressed_size': uncompressed_size,
            'compressed_size': compressed_size,
            'compression_ratio': compression_ratio,
            'file_count': file_count,
            'duration': duration
        }

    except Exception as e:
        logger.error(f"Failed to create tarball: {e}")
        raise


def extract_tarball_via_ssh(
    ssh_manager,
    remote_archive_path: str,
    remote_extract_path: str,
    cleanup_archive: bool = True,
    tracker=None
) -> dict:
    """
    Extract a tar.gz archive on remote server via SSH command.

    This is more efficient than using SFTP to extract, as it runs
    natively on the remote system.

    Args:
        ssh_manager: SSH manager instance
        remote_archive_path: Path to .tar.gz on remote server
        remote_extract_path: Directory to extract into
        cleanup_archive: Whether to delete archive after extraction
        tracker: Optional progress tracker

    Returns:
        Dict with:
        - status: "success" or "error"
        - extracted_path: Path where files were extracted
        - duration: Time taken in seconds
        - error: Error message if failed
    """

    start_time = datetime.now()

    logger.info(f"Extracting tarball on remote: {remote_archive_path} -> {remote_extract_path}")

    # Update progress to extracting phase
    if tracker:
        tracker.update(phase="extracting", status="in_progress")

    try:
        # Ensure extract directory exists
        mkdir_cmd = f"mkdir -p {remote_extract_path}"
        result = ssh_manager.execute_command(mkdir_cmd, timeout=30)

        # Extract tar.gz
        # -x: extract, -z: gzip, -f: file
        # -C: change to directory before extracting
        extract_cmd = f"tar -xzf {remote_archive_path} -C {remote_extract_path}"
        result = ssh_manager.execute_command(extract_cmd, timeout=300)

        # Check if extraction succeeded (exit code check would be ideal)
        if "error" in result.stderr.lower() or "cannot" in result.stderr.lower():
            raise Exception(f"Extraction failed: {result.stderr}")

        # Cleanup archive if requested
        if cleanup_archive:
            cleanup_cmd = f"rm {remote_archive_path}"
            ssh_manager.execute_command(cleanup_cmd, timeout=30)
            logger.info(f"Cleaned up remote archive: {remote_archive_path}")

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Extraction completed in {duration:.1f}s")

        return {
            'status': 'success',
            'extracted_path': remote_extract_path,
            'duration': duration,
            'error': None
        }

    except Exception as e:
        logger.error(f"Failed to extract tarball on remote: {e}")
        return {
            'status': 'error',
            'extracted_path': remote_extract_path,
            'duration': (datetime.now() - start_time).total_seconds(),
            'error': str(e)
        }
