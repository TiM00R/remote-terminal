"""
SFTP File Transfer Tools for Remote Terminal MCP Server

Phase 1 - Single File Operations (Original)
Phase 2 - Directory Operations (Enhanced with Phase 2.5)
Phase 2.5 - Smart Transfer with Compression and Progress

This module orchestrates all SFTP operations using modular components:
- Decision logic (sftp_decisions.py)
- Compression (sftp_compression.py)
- Progress tracking (sftp_progress.py)
- Standard transfer (sftp_transfer_standard.py)
- Compressed transfer (sftp_transfer_compressed.py)

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import os
import stat
import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import paramiko

# Import Phase 1 helpers (keep these)
from .sftp_decisions import (
    decide_compression,
    estimate_transfer_time,
    decide_background_mode,
    analyze_file_list,
    make_transfer_decisions,
    TEXT_EXTENSIONS
)
from .sftp_compression import (
    compress_and_upload,
    download_and_extract
)
from .sftp_progress import (
    TransferProgress,
    ProgressTracker,
    format_duration,
    format_speed
)
from .sftp_transfer_standard import (
    execute_standard_upload,
    execute_standard_download,
    scan_local_directory,
    scan_remote_directory
)
from .sftp_transfer_compressed import (
    execute_compressed_upload,
    execute_compressed_download
)

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions (Phase 1 - Keep as is)
# ============================================================================

class SFTPError(Exception):
    """Base SFTP error"""
    pass


class SFTPConnectionError(SFTPError):
    """SFTP connection not available"""
    pass


class SFTPPermissionError(SFTPError):
    """Permission denied"""
    pass


class SFTPFileNotFoundError(SFTPError):
    """File or directory not found"""
    pass


class SFTPFileExistsError(SFTPError):
    """File exists and overwrite=False"""
    pass


class SFTPConflictError(SFTPError):
    """Directory conflict with if_exists policy"""
    pass


# ============================================================================
# Helper Functions (Phase 1 - Keep as is)
# ============================================================================

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_permissions(mode: int) -> str:
    """Convert numeric permissions to octal string format."""
    return f"0{mode & 0o777:o}"


def timestamp_to_iso(timestamp: float) -> str:
    """Convert Unix timestamp to ISO format string."""
    return datetime.fromtimestamp(timestamp).isoformat() + 'Z'


def validate_path(path: str, path_type: str = "path") -> None:
    """
    Validate a file path for security issues.
    
    Args:
        path: Path to validate
        path_type: Type of path (for error messages)
        
    Raises:
        ValueError: If path contains security issues
    """
    if not path:
        raise ValueError(f"{path_type} cannot be empty")
    
    # Normalize path
    normalized = os.path.normpath(path)
    
    # Check for path traversal attempts
    if '..' in normalized:
        raise ValueError(f"Path traversal detected in {path_type}: {path}")


def get_sftp_client(ssh_manager) -> paramiko.SFTPClient:
    """
    Get SFTP client from SSH manager.
    
    Args:
        ssh_manager: SSH manager instance
        
    Returns:
        SFTP client
        
    Raises:
        SFTPConnectionError: If SFTP connection not available
    """
    if not ssh_manager.is_connected():
        raise SFTPConnectionError("SSH not connected. Use select_server first.")
    
    try:
        return ssh_manager.get_sftp()
    except Exception as e:
        logger.error(f"Failed to get SFTP client: {e}")
        raise SFTPConnectionError(f"Failed to establish SFTP connection: {e}")


def get_default_exclude_patterns() -> List[str]:
    """Get default exclude patterns for common unwanted files/directories."""
    return [
        '.git',
        '.git/**',
        '__pycache__',
        '__pycache__/**',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.Python',
        'node_modules',
        'node_modules/**',
        '.venv',
        '.venv/**',
        'venv',
        'venv/**',
        '.env',
        '.DS_Store',
        'Thumbs.db',
        '*.swp',
        '*.swo',
        '*~',
        '.idea',
        '.idea/**',
        '.vscode',
        '.vscode/**',
        '*.log'
    ]


# ============================================================================
# Phase 1: Single File Operations (Keep as is)
# ============================================================================

async def sftp_upload_file(
    ssh_manager,
    local_path: str,
    remote_path: str,
    overwrite: bool = True,
    chmod: Optional[int] = None,
    preserve_timestamp: bool = True
) -> Dict[str, Any]:
    """Upload a single file from local machine to remote server."""
    start_time = datetime.now()
    
    validate_path(local_path, "local_path")
    validate_path(remote_path, "remote_path")
    
    if not os.path.isfile(local_path):
        raise SFTPFileNotFoundError(f"Local file not found: {local_path}")
    
    local_size = os.path.getsize(local_path)
    
    if local_size > 100 * 1024 * 1024:
        size_str = format_file_size(local_size)
        logger.warning(f"Large file upload: {local_path} ({size_str}), may take several minutes")
    
    sftp = get_sftp_client(ssh_manager)
    
    file_existed = False
    try:
        sftp.stat(remote_path)
        file_existed = True
        if not overwrite:
            raise SFTPFileExistsError(f"Remote file exists and overwrite=False: {remote_path}")
    except FileNotFoundError:
        pass
    
    logger.info(f"Uploading file: {local_path} → {remote_path} ({format_file_size(local_size)})")
    
    try:
        sftp.put(local_path, remote_path)
        
        chmod_applied = None
        if chmod is not None:
            sftp.chmod(remote_path, chmod)
            chmod_applied = format_permissions(chmod)
            logger.info(f"Applied permissions {chmod_applied} to {remote_path}")
        
        timestamp_preserved = False
        if preserve_timestamp:
            local_stat = os.stat(local_path)
            sftp.utime(remote_path, (local_stat.st_atime, local_stat.st_mtime))
            timestamp_preserved = True
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Upload completed in {duration:.3f}s ({format_file_size(local_size)})")
        
        return {
            "status": "success",
            "local_path": local_path,
            "remote_path": remote_path,
            "bytes_transferred": local_size,
            "duration": duration,
            "file_existed": file_existed,
            "chmod_applied": chmod_applied,
            "timestamp_preserved": timestamp_preserved,
            "error": None
        }
        
    except PermissionError as e:
        raise SFTPPermissionError(f"Permission denied: {remote_path}")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise SFTPError(f"Upload failed: {e}")


async def sftp_download_file(
    ssh_manager,
    remote_path: str,
    local_path: str,
    overwrite: bool = True,
    preserve_timestamp: bool = True
) -> Dict[str, Any]:
    """Download a single file from remote server to local machine."""
    start_time = datetime.now()
    
    validate_path(remote_path, "remote_path")
    validate_path(local_path, "local_path")
    
    file_existed = os.path.isfile(local_path)
    if file_existed and not overwrite:
        raise SFTPFileExistsError(f"Local file exists and overwrite=False: {local_path}")
    
    sftp = get_sftp_client(ssh_manager)
    
    try:
        remote_stat = sftp.stat(remote_path)
        remote_size = remote_stat.st_size
    except FileNotFoundError:
        raise SFTPFileNotFoundError(f"Remote file not found: {remote_path}")
    
    if remote_size > 100 * 1024 * 1024:
        size_str = format_file_size(remote_size)
        logger.warning(f"Large file download: {remote_path} ({size_str}), may take several minutes")
    
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
        logger.info(f"Created local directory: {local_dir}")
    
    logger.info(f"Downloading file: {remote_path} → {local_path} ({format_file_size(remote_size)})")
    
    try:
        sftp.get(remote_path, local_path)
        
        timestamp_preserved = False
        if preserve_timestamp:
            os.utime(local_path, (remote_stat.st_atime, remote_stat.st_mtime))
            timestamp_preserved = True
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Download completed in {duration:.3f}s ({format_file_size(remote_size)})")
        
        return {
            "status": "success",
            "remote_path": remote_path,
            "local_path": local_path,
            "bytes_transferred": remote_size,
            "duration": duration,
            "file_existed": file_existed,
            "timestamp_preserved": timestamp_preserved,
            "error": None
        }
        
    except PermissionError as e:
        raise SFTPPermissionError(f"Permission denied: {local_path}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise SFTPError(f"Download failed: {e}")


async def sftp_list_directory(
    ssh_manager,
    remote_path: str,
    recursive: bool = False,
    show_hidden: bool = False
) -> Dict[str, Any]:
    """List contents of a remote directory."""
    validate_path(remote_path, "remote_path")
    
    sftp = get_sftp_client(ssh_manager)
    
    try:
        dir_stat = sftp.stat(remote_path)
        if not stat.S_ISDIR(dir_stat.st_mode):
            raise SFTPError(f"Path is not a directory: {remote_path}")
    except FileNotFoundError:
        raise SFTPFileNotFoundError(f"Remote directory not found: {remote_path}")
    
    logger.info(f"Listing directory: {remote_path} (recursive={recursive})")
    
    items = []
    total_files = 0
    total_dirs = 0
    total_size = 0
    
    def scan_directory(path: str):
        nonlocal total_files, total_dirs, total_size
        
        try:
            for attr in sftp.listdir_attr(path):
                if not show_hidden and attr.filename.startswith('.'):
                    continue
                
                full_path = f"{path}/{attr.filename}".replace('//', '/')
                
                if stat.S_ISDIR(attr.st_mode):
                    item_type = "directory"
                    total_dirs += 1
                elif stat.S_ISLNK(attr.st_mode):
                    item_type = "symlink"
                elif stat.S_ISREG(attr.st_mode):
                    item_type = "file"
                    total_files += 1
                    total_size += attr.st_size
                else:
                    item_type = "unknown"
                
                item = {
                    "name": attr.filename,
                    "path": full_path,
                    "type": item_type,
                    "size": attr.st_size,
                    "permissions": format_permissions(attr.st_mode),
                    "modified": timestamp_to_iso(attr.st_mtime)
                }
                
                items.append(item)
                
                if recursive and item_type == "directory":
                    scan_directory(full_path)
                    
        except Exception as e:
            logger.warning(f"Error scanning directory {path}: {e}")
    
    try:
        scan_directory(remote_path)
        
        return {
            "status": "success",
            "path": remote_path,
            "total_files": total_files,
            "total_dirs": total_dirs,
            "total_size": total_size,
            "items": items,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Directory listing failed: {e}")
        raise SFTPError(f"Directory listing failed: {e}")


async def sftp_get_file_info(
    ssh_manager,
    remote_path: str
) -> Dict[str, Any]:
    """Get detailed information about a remote file or directory."""
    validate_path(remote_path, "remote_path")
    
    sftp = get_sftp_client(ssh_manager)
    
    logger.info(f"Getting file info: {remote_path}")
    
    try:
        file_stat = sftp.lstat(remote_path)
        
        if stat.S_ISDIR(file_stat.st_mode):
            item_type = "directory"
        elif stat.S_ISLNK(file_stat.st_mode):
            item_type = "symlink"
        elif stat.S_ISREG(file_stat.st_mode):
            item_type = "file"
        else:
            item_type = "unknown"
        
        return {
            "status": "success",
            "path": remote_path,
            "exists": True,
            "type": item_type,
            "size": file_stat.st_size,
            "permissions": format_permissions(file_stat.st_mode),
            "owner_uid": file_stat.st_uid,
            "group_gid": file_stat.st_gid,
            "modified": timestamp_to_iso(file_stat.st_mtime),
            "accessed": timestamp_to_iso(file_stat.st_atime),
            "error": None
        }
        
    except FileNotFoundError:
        return {
            "status": "success",
            "path": remote_path,
            "exists": False,
            "error": None
        }
    except PermissionError:
        raise SFTPPermissionError(f"Permission denied: {remote_path}")
    except Exception as e:
        logger.error(f"Get file info failed: {e}")
        raise SFTPError(f"Get file info failed: {e}")


# ============================================================================
# Phase 2.5: Smart Directory Operations
# ============================================================================

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


# ============================================================================
# Background Execution Helpers
# ============================================================================

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


# ============================================================================
# MCP Tool Registration
# ============================================================================

async def get_tools(**kwargs):
    """Get list of SFTP tools for MCP registration"""
    from mcp import types
    
    return [
        # Phase 1: Single file operations
        types.Tool(
            name="upload_file",
            description="Upload a file from local machine to remote server via SFTP",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path to local file (e.g., 'C:/Users/Tim/config.json')"
                    },
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/config.json')"
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, error if remote file exists (default: true)",
                        "default": True
                    },
                    "chmod": {
                        "type": "integer",
                        "description": "Optional octal permissions in decimal (e.g., 493 for 0o755)",
                        "default": None
                    },
                    "preserve_timestamp": {
                        "type": "boolean",
                        "description": "Copy local modification time to remote file (default: true)",
                        "default": True
                    }
                },
                "required": ["local_path", "remote_path"]
            }
        ),
        types.Tool(
            name="download_file",
            description="Download a file from remote server to local machine via SFTP",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/app.log')"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path for local destination (e.g., 'C:/Downloads/app.log')"
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If false, error if local file exists (default: true)",
                        "default": True
                    },
                    "preserve_timestamp": {
                        "type": "boolean",
                        "description": "Copy remote modification time to local file (default: true)",
                        "default": True
                    }
                },
                "required": ["remote_path", "local_path"]
            }
        ),
        types.Tool(
            name="list_remote_directory",
            description="List contents of a remote directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Remote directory path (e.g., '/home/tstat')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Traverse subdirectories (default: false)",
                        "default": False
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Include files starting with '.' (default: false)",
                        "default": False
                    }
                },
                "required": ["remote_path"]
            }
        ),
        types.Tool(
            name="get_remote_file_info",
            description="Get detailed information about a remote file or directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Remote file or directory path (e.g., '/home/tstat/config.json')"
                    }
                },
                "required": ["remote_path"]
            }
        ),
        
        # Phase 2.5: Smart directory operations
        types.Tool(
            name="upload_directory",
            description="Smart directory upload with automatic compression and progress tracking. Automatically decides whether to use compression and background mode based on transfer characteristics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path to local directory (e.g., 'C:/Projects/myapp')"
                    },
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/myapp')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Include subdirectories (default: true)",
                        "default": True
                    },
                    "if_exists": {
                        "type": "string",
                        "enum": ["merge", "overwrite", "skip", "error"],
                        "description": "Conflict resolution: 'merge' (default), 'overwrite', 'skip', 'error'",
                        "default": "merge"
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (None = use defaults: .git, __pycache__, node_modules, etc.)",
                        "default": None
                    },
                    "chmod_files": {
                        "type": "integer",
                        "description": "File permissions in decimal (e.g., 420 for 0o644)",
                        "default": None
                    },
                    "chmod_dirs": {
                        "type": "integer",
                        "description": "Directory permissions in decimal (e.g., 493 for 0o755)",
                        "default": None
                    },
                    "preserve_timestamps": {
                        "type": "boolean",
                        "description": "Copy local modification times (default: true)",
                        "default": True
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["auto", "always", "never"],
                        "description": "Compression mode: 'auto' (default), 'always', 'never'",
                        "default": "auto"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Background mode: null = auto-decide, true = force, false = block",
                        "default": None
                    }
                },
                "required": ["local_path", "remote_path"]
            }
        ),
        types.Tool(
            name="download_directory",
            description="Smart directory download with automatic compression and progress tracking. Automatically decides whether to use compression and background mode based on transfer characteristics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {
                        "type": "string",
                        "description": "Absolute path on remote server (e.g., '/home/tstat/myapp')"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Absolute path for local destination (e.g., 'C:/Projects/myapp')"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Include subdirectories (default: true)",
                        "default": True
                    },
                    "if_exists": {
                        "type": "string",
                        "enum": ["merge", "overwrite", "skip", "error"],
                        "description": "Conflict resolution: 'merge' (default), 'overwrite', 'skip', 'error'",
                        "default": "merge"
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (None = use defaults)",
                        "default": None
                    },
                    "preserve_timestamps": {
                        "type": "boolean",
                        "description": "Copy remote modification times (default: true)",
                        "default": True
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["auto", "always", "never"],
                        "description": "Compression mode: 'auto' (default), 'always', 'never'",
                        "default": "auto"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Background mode: null = auto-decide, true = force, false = block",
                        "default": None
                    }
                },
                "required": ["remote_path", "local_path"]
            }
        )
    ]


async def handle_call(name: str, arguments: dict, shared_state, **kwargs):
    """
    Main handler for SFTP tool calls.
    Routes to specific tool functions.
    
    Args:
        name: Tool name
        arguments: Tool arguments
        shared_state: Shared state with SSH manager
        **kwargs: Other dependencies
        
    Returns:
        List of TextContent responses for MCP protocol, or None if tool not handled
    """
    from mcp import types
    
    # Check if this is one of our tools
    valid_tools = [
        "upload_file", "download_file", "list_remote_directory", "get_remote_file_info",
        "upload_directory", "download_directory"
    ]
    
    if name not in valid_tools:
        return None
    
    ssh_manager = shared_state.ssh_manager
    # Auto-start web terminal for SFTP transfers to show progress
    web_server = kwargs.get('web_server')
    if web_server and not web_server.is_running():
        if name in ['upload_directory', 'download_directory', 'upload_file', 'download_file']:
            try:
                web_server.start()
                logger.info("Auto-started web terminal for SFTP transfer progress")
            except Exception as e:
                logger.warning(f"Could not auto-start web terminal: {e}")
    
                
    try:
        # Phase 1: Single file operations
        if name == "upload_file":
            result = await sftp_upload_file(
                ssh_manager=ssh_manager,
                local_path=arguments['local_path'],
                remote_path=arguments['remote_path'],
                overwrite=arguments.get('overwrite', True),
                chmod=arguments.get('chmod'),
                preserve_timestamp=arguments.get('preserve_timestamp', True)
            )
            
        elif name == "download_file":
            result = await sftp_download_file(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                local_path=arguments['local_path'],
                overwrite=arguments.get('overwrite', True),
                preserve_timestamp=arguments.get('preserve_timestamp', True)
            )
            
        elif name == "list_remote_directory":
            result = await sftp_list_directory(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                recursive=arguments.get('recursive', False),
                show_hidden=arguments.get('show_hidden', False)
            )
            
        elif name == "get_remote_file_info":
            result = await sftp_get_file_info(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path']
            )
        
        # Phase 2.5: Smart directory operations
        elif name == "upload_directory":
            result = await sftp_upload_directory(
                ssh_manager=ssh_manager,
                local_path=arguments['local_path'],
                remote_path=arguments['remote_path'],
                recursive=arguments.get('recursive', True),
                if_exists=arguments.get('if_exists', 'merge'),
                exclude_patterns=arguments.get('exclude_patterns'),
                chmod_files=arguments.get('chmod_files'),
                chmod_dirs=arguments.get('chmod_dirs'),
                preserve_timestamps=arguments.get('preserve_timestamps', True),
                compression=arguments.get('compression', 'auto'),
                background=arguments.get('background'),
                shared_state=shared_state
            )
            
        elif name == "download_directory":
            result = await sftp_download_directory(
                ssh_manager=ssh_manager,
                remote_path=arguments['remote_path'],
                local_path=arguments['local_path'],
                recursive=arguments.get('recursive', True),
                if_exists=arguments.get('if_exists', 'merge'),
                exclude_patterns=arguments.get('exclude_patterns'),
                preserve_timestamps=arguments.get('preserve_timestamps', True),
                compression=arguments.get('compression', 'auto'),
                background=arguments.get('background'),
                shared_state=shared_state
            )
        
        # Return success response
        import json
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
    except SFTPError as e:
        # Return error response
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
        if 'local_path' in arguments:
            error_result['local_path'] = arguments['local_path']
        if 'remote_path' in arguments:
            error_result['remote_path'] = arguments['remote_path']
        
        import json
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    except Exception as e:
        logger.error(f"Unexpected error in SFTP tool {name}: {e}", exc_info=True)
        error_result = {
            "status": "error",
            "error": f"Unexpected error: {e}",
            "error_type": "UnexpectedError"
        }
        import json
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]
