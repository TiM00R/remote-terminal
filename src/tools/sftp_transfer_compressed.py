"""
SFTP Compressed Transfer

Compressed transfer operations using tar.gz for efficient directory transfer.
Best for directories with many small files or text-heavy projects.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.1 - FIXED: Pass tracker to compression functions for progress updates
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .sftp_compression import (
    compress_and_upload,
    download_and_extract
)

logger = logging.getLogger(__name__)


def execute_compressed_upload(
    ssh_manager,
    sftp,
    files: list,
    local_root: str,
    remote_root: str,
    exclude_patterns: list,
    chmod_dirs: Optional[int],
    tracker
) -> Dict[str, Any]:
    """
    Execute compressed upload workflow.
    
    Workflow:
    1. Create tar.gz locally (with progress)
    2. Upload single archive (with progress)
    3. Extract on remote (with progress)
    4. Cleanup temporary files
    
    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        files: List of file dicts
        local_root: Local root directory
        remote_root: Remote root directory
        exclude_patterns: Patterns to exclude
        chmod_dirs: Optional directory permissions
        tracker: Progress tracker instance
        
    Returns:
        Dict with transfer statistics
    """
    
    start_time = datetime.now()
    
    try:
        # Set initial phase
        tracker.update(phase="compressing", status="in_progress")
        logger.info("Starting compressed upload...")
        
        # Perform compression and upload (tracker is passed through)
        result = compress_and_upload(
            ssh_manager=ssh_manager,
            sftp=sftp,
            local_dir=local_root,
            remote_dir=remote_root,
            exclude_patterns=exclude_patterns,
            chmod_dirs=chmod_dirs,
            tracker=tracker  # CRITICAL: Pass tracker for progress updates
        )
        
        if result['status'] != 'success':
            raise Exception(f"Compressed upload failed: {result.get('error', 'Unknown error')}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Build statistics matching standard transfer format
        stats = {
            'files_uploaded': 1,
            'files_skipped': 0,
            'files_overwritten': 0,
            'dirs_created': 1,  # Remote root
            'bytes_transferred': result['uncompressed_size']
        }
        
        return {
            'status': 'success',
            'method': 'compressed',
            'statistics': stats,
            'skipped_files': [],
            'skipped_count': 0,
            'duration': duration,
            'compression_info': {
                'uncompressed_size': result['uncompressed_size'],
                'compressed_size': result['compressed_size'],
                'compression_ratio': result['compression_ratio'],
                'compression_duration': result['compression_duration'],
                'upload_duration': result['upload_duration'],
                'extraction_duration': result['extraction_duration']
            }
        }
        
    except Exception as e:
        logger.error(f"Compressed upload failed: {e}")
        tracker.add_error(local_root, str(e))
        
        return {
            'status': 'error',
            'method': 'compressed',
            'error': str(e),
            'duration': (datetime.now() - start_time).total_seconds()
        }


def execute_compressed_download(
    ssh_manager,
    sftp,
    files: list,
    remote_root: str,
    local_root: str,
    exclude_patterns: list,
    tracker
) -> Dict[str, Any]:
    """
    Execute compressed download workflow.
    
    Workflow:
    1. Create tar.gz on remote (with progress)
    2. Download single archive (with progress)
    3. Extract locally (with progress)
    4. Cleanup temporary files
    
    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        files: List of file dicts
        remote_root: Remote root directory
        local_root: Local root directory
        exclude_patterns: Patterns to exclude
        tracker: Progress tracker instance
        
    Returns:
        Dict with transfer statistics
    """
    
    start_time = datetime.now()
    
    try:
        # Set initial phase
        tracker.update(phase="compressing", status="in_progress")
        logger.info("Starting compressed download...")
        
        # Perform compression, download, and extraction (tracker is passed through)
        result = download_and_extract(
            ssh_manager=ssh_manager,
            sftp=sftp,
            remote_dir=remote_root,
            local_dir=local_root,
            exclude_patterns=exclude_patterns,
            tracker=tracker  # CRITICAL: Pass tracker for progress updates
        )
        
        if result['status'] != 'success':
            raise Exception(f"Compressed download failed: {result.get('error', 'Unknown error')}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Build statistics matching standard transfer format
        stats = {
            'files_downloaded': 1,
            'files_skipped': 0,
            'files_overwritten': 0,
            'dirs_created': 1,  # Local root
            'bytes_transferred': result['compressed_size']  # Use compressed size
        }
        
        return {
            'status': 'success',
            'method': 'compressed',
            'statistics': stats,
            'skipped_files': [],
            'skipped_count': 0,
            'duration': duration,
            'compression_info': {
                'compressed_size': result['compressed_size'],
                'compression_duration': result['compression_duration'],
                'download_duration': result['download_duration'],
                'extraction_duration': result['extraction_duration']
            }
        }
        
    except Exception as e:
        logger.error(f"Compressed download failed: {e}")
        tracker.add_error(remote_root, str(e))
        
        return {
            'status': 'error',
            'method': 'compressed',
            'error': str(e),
            'duration': (datetime.now() - start_time).total_seconds()
        }


def estimate_compressed_size(total_size: int, text_ratio: float = 0.5) -> int:
    """
    Estimate compressed size based on content type.
    
    Args:
        total_size: Uncompressed size in bytes
        text_ratio: Ratio of text files (0.0 to 1.0)
        
    Returns:
        Estimated compressed size in bytes
    """
    # Text files: 70-80% compression (0.2-0.3 remaining)
    # Binary files: 10-20% compression (0.8-0.9 remaining)
    
    TEXT_COMPRESSION = 0.25  # Text compresses to 25% of original
    BINARY_COMPRESSION = 0.85  # Binary compresses to 85% of original
    
    text_size = total_size * text_ratio
    binary_size = total_size * (1 - text_ratio)
    
    compressed_text = text_size * TEXT_COMPRESSION
    compressed_binary = binary_size * BINARY_COMPRESSION
    
    return int(compressed_text + compressed_binary)
