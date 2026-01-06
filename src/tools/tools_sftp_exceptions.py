"""
SFTP Exception Classes

Custom exception hierarchy for SFTP operations.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""


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
