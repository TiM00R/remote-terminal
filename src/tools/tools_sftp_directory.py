"""
SFTP Directory Operations

Smart directory upload/download with automatic optimization, compression, and background execution.

Author: Phase 2.5 Smart Transfer Implementation
Date: 2025-11-13
Version: 3.0
"""

import logging

logger = logging.getLogger(__name__)

# Import from split modules
from .tools_sftp_directory_upload import (
    sftp_upload_directory
)
from .tools_sftp_directory_download import (
    sftp_download_directory
)
