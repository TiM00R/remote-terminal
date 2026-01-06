"""
SFTP Compression Helpers

This module provides tar.gz compression and extraction utilities for
efficient directory transfer.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.3 - FIXED: Reset completed_files to 0 when switching to transfer phase
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

from tools.sftp_compression_tar import create_tarball, extract_tarball_via_ssh
from tools.sftp_compression_upload import compress_and_upload
from tools.sftp_compression_download import download_and_extract
