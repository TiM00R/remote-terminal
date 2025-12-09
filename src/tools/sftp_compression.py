"""
SFTP Compression Helpers

This module provides tar.gz compression and extraction utilities for
efficient directory transfer.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.3 - FIXED: Reset completed_files to 0 when switching to transfer phase
"""

import os
import tarfile
import tempfile
import logging
from pathlib import Path
import time
from typing import List, Optional
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
