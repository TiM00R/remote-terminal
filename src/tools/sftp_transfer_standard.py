"""
SFTP Standard Transfer

Standard file-by-file transfer operations for directories.
Used when compression is not beneficial.

Author: Smart Transfer Implementation
Date: 2025-11-13  
Version: 1.2 - FIXED: Set status to "completed" when transfer finishes
"""

import os
import stat
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def execute_standard_upload(
    ssh_manager,
    sftp,
    files: List[Dict],
    local_root: str,
    remote_root: str,
    if_exists: str,
    chmod_files: Optional[int],
    chmod_dirs: Optional[int],
    preserve_timestamps: bool,
    tracker
) -> Dict[str, Any]:
    """
    Execute standard file-by-file upload.
    
    Args:
        ssh_manager: SSH manager instance
        sftp: SFTP client
        files: List of file dicts with 'local_path', 'rel_path', 'size'
        local_root: Local root directory
        remote_root: Remote root directory
        if_exists: Conflict resolution policy
        chmod_files: Optional file permissions
        chmod_dirs: Optional directory permissions
        preserve_timestamps: Whether to preserve timestamps
        tracker: Progress tracker instance
        
    Returns:
        Dict with transfer statistics
    """
    
    start_time = datetime.now()
    
    stats = {
        'files_uploaded': 0,
        'files_skipped': 0,
        'files_overwritten': 0,
        'dirs_created': 0,
        'bytes_transferred': 0
    }
    
    skipped_files = []
    created_dirs = set()
    
    # Ensure remote root exists
    try:
        sftp.stat(remote_root)
    except FileNotFoundError:
        sftp.mkdir(remote_root)
        if chmod_dirs is not None:
            sftp.chmod(remote_root, chmod_dirs)
        stats['dirs_created'] += 1
        logger.info(f"Created remote root directory: {remote_root}")
    
    # FIX: Set phase to transferring for standard transfers
    tracker.update(phase="transferring", status="in_progress")
    
    # Transfer each file
    for idx, file_info in enumerate(files):
        local_path = file_info['local_path']
        rel_path = file_info['rel_path']
        file_size = file_info['size']
        
        remote_path = f"{remote_root}/{rel_path}".replace('//', '/')
        
        try:
            # Create remote parent directories if needed
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and remote_dir not in created_dirs:
                _ensure_remote_directory(sftp, remote_dir, chmod_dirs)
                created_dirs.add(remote_dir)
                stats['dirs_created'] += 1
            
            # Check if remote file exists
            file_exists = False
            try:
                sftp.stat(remote_path)
                file_exists = True
            except FileNotFoundError:
                pass
            
            # Apply if_exists policy
            should_upload = True
            if file_exists:
                if if_exists == "skip":
                    should_upload = False
                    stats['files_skipped'] += 1
                    skipped_files.append(rel_path)
                    logger.debug(f"Skipped existing file: {remote_path}")
                elif if_exists == "overwrite" or if_exists == "merge":
                    stats['files_overwritten'] += 1
            
            # Upload file
            if should_upload:
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
                
                # Upload with progress callback
                sftp.put(local_path, remote_path, callback=file_callback)
                
                # Apply chmod if specified
                if chmod_files is not None:
                    sftp.chmod(remote_path, chmod_files)
                
                # Preserve timestamp if requested
                if preserve_timestamps:
                    local_stat = os.stat(local_path)
                    sftp.utime(remote_path, (local_stat.st_atime, local_stat.st_mtime))
                
                stats['files_uploaded'] += 1
                stats['bytes_transferred'] += file_size
                
                logger.debug(f"Uploaded: {rel_path} ({file_size} bytes)")
        
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
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


def _ensure_remote_directory(sftp, remote_dir: str, chmod: Optional[int] = None):
    """
    Ensure a remote directory exists, creating parent directories as needed.
    
    Args:
        sftp: SFTP client
        remote_dir: Remote directory path
        chmod: Optional permissions to set
    """
    # Split path into parts
    parts = remote_dir.split('/')
    current_path = ""
    
    for part in parts:
        if not part:
            continue
        
        current_path = f"{current_path}/{part}" if current_path else f"/{part}"
        
        try:
            sftp.stat(current_path)
        except FileNotFoundError:
            # Directory doesn't exist, create it
            sftp.mkdir(current_path)
            if chmod is not None:
                sftp.chmod(current_path, chmod)
            logger.debug(f"Created remote directory: {current_path}")


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
