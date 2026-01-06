"""
SFTP Standard Transfer

Standard file-by-file transfer operations for directories.
Used when compression is not beneficial.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.2 - FIXED: Set status to "completed" when transfer finishes
"""

import logging

logger = logging.getLogger(__name__)

# Import from split modules
from .sftp_transfer_upload import execute_standard_upload
from .sftp_transfer_download import execute_standard_download
from .sftp_transfer_scan import scan_local_directory, scan_remote_directory
