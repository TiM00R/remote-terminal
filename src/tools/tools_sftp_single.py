"""
SFTP Single File Operations

Functions for uploading, downloading, listing, and getting info about single files.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import os
import stat
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .tools_sftp_exceptions import (
    SFTPError,
    SFTPPermissionError,
    SFTPFileNotFoundError,
    SFTPFileExistsError
)
from .tools_sftp_utils import (
    format_file_size,
    format_permissions,
    timestamp_to_iso,
    validate_path,
    get_sftp_client
)

logger = logging.getLogger(__name__)


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
