"""
SFTP Transfer Decision Logic

This module provides heuristics and decision-making for:
- When to use compression vs standard transfer
- When to use background vs blocking mode
- Transfer time estimation

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.0
"""

import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


# Text file extensions that compress well
TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.txt', '.md', '.rst', '.tex',
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.html', '.htm', '.css', '.scss', '.sass', '.less',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.sql', '.go', '.rs', '.php', '.rb', '.pl', '.lua', '.r',
    '.csv', '.tsv', '.log',
    '.gitignore', '.dockerignore', '.editorconfig',
    'Makefile', 'Dockerfile', 'Jenkinsfile'
}


def decide_compression(
    file_count: int,
    total_size: int,
    text_ratio: float = None
) -> bool:
    """
    Decide whether to use compression based on transfer characteristics.
    
    Compression helps when:
    - Many small files (reduces SFTP overhead)
    - Mostly text files (good compression ratio)
    - Medium to large total size (overhead worth it)
    
    Compression doesn't help when:
    - Few large files (already efficient)
    - Small total size (overhead not worth it)
    - Already compressed files (images, videos)
    
    Args:
        file_count: Number of files to transfer
        total_size: Total size in bytes
        text_ratio: Optional ratio of text files (0.0 to 1.0)
        
    Returns:
        True if compression should be used
    """
    
    # Rule 1: Many small files -> ALWAYS compress
    # SFTP overhead (~50ms per file) dominates
    if file_count > 100:
        logger.info(f"Compression decision: YES (many files: {file_count})")
        return True
    
    # Rule 2: Mostly text files -> Compress
    # Text files compress 3-5x typically
    if text_ratio is not None and text_ratio > 0.6:
        logger.info(f"Compression decision: YES (text ratio: {text_ratio:.1%})")
        return True
    
    # Rule 3: Few large files -> DON'T compress
    # SFTP is already efficient for large files
    # Compression overhead not worth it for binary/media files
    if file_count < 10 and total_size > 100 * 1024 * 1024:
        logger.info(f"Compression decision: NO (few large files: {file_count} files, {total_size/(1024*1024):.1f}MB)")
        return False
    
    # Rule 4: Small total size -> DON'T compress
    # Overhead (compression, extraction) not worth it
    if total_size < 1 * 1024 * 1024:  # < 1MB
        logger.info(f"Compression decision: NO (small size: {total_size/1024:.1f}KB)")
        return False
    
    # Rule 5: Default heuristic
    # Use compression if >50 files OR >10MB
    decision = file_count > 50 or total_size > 10 * 1024 * 1024
    
    logger.info(f"Compression decision: {'YES' if decision else 'NO'} "
                f"(files={file_count}, size={total_size/(1024*1024):.1f}MB)")
    
    return decision


def estimate_transfer_time(
    file_count: int,
    total_size: int,
    use_compression: bool,
    network_speed_mbps: float = 10.0  # MB/s, configurable
) -> float:
    """
    Estimate transfer time in seconds.
    
    Factors considered:
    - Network speed (default: 10 MB/s for local network)
    - SFTP per-file overhead (~50ms per file)
    - Compression time (if applicable)
    - Extraction time (if applicable)
    
    Args:
        file_count: Number of files
        total_size: Total size in bytes
        use_compression: Whether compression will be used
        network_speed_mbps: Network speed in MB/s
        
    Returns:
        Estimated time in seconds
    """
    
    # Convert network speed to bytes/sec
    NETWORK_SPEED = network_speed_mbps * 1024 * 1024
    
    # SFTP overhead per file operation
    FILE_OVERHEAD_SEC = 0.05  # 50ms per file
    
    if use_compression:
        # Compression workflow:
        # 1. Compress locally (~50 MB/s)
        # 2. Transfer single compressed file
        # 3. Extract remotely (~100 MB/s)
        
        COMPRESSION_SPEED = 50 * 1024 * 1024  # 50 MB/s
        EXTRACTION_SPEED = 100 * 1024 * 1024  # 100 MB/s
        
        # Assume 50% compression ratio for mixed files
        # (Text: 70-80%, binary: 10-20%, average: ~50%)
        COMPRESSION_RATIO = 0.5
        
        compression_time = total_size / COMPRESSION_SPEED
        compressed_size = total_size * COMPRESSION_RATIO
        transfer_time = compressed_size / NETWORK_SPEED
        extraction_time = compressed_size / EXTRACTION_SPEED
        
        # Add overhead for tar creation and SSH command execution
        overhead = 2.0  # 2 seconds for setup/cleanup
        
        total_time = compression_time + transfer_time + extraction_time + overhead
        
        logger.debug(f"Time estimate (compressed): compress={compression_time:.1f}s, "
                    f"transfer={transfer_time:.1f}s, extract={extraction_time:.1f}s, "
                    f"total={total_time:.1f}s")
        
        return total_time
    else:
        # Standard workflow:
        # 1. Per-file overhead for each file
        # 2. Transfer time based on total size
        
        overhead_time = file_count * FILE_OVERHEAD_SEC
        transfer_time = total_size / NETWORK_SPEED
        
        total_time = overhead_time + transfer_time
        
        logger.debug(f"Time estimate (standard): overhead={overhead_time:.1f}s, "
                    f"transfer={transfer_time:.1f}s, total={total_time:.1f}s")
        
        return total_time


def decide_background_mode(
    estimated_time: float,
    threshold_seconds: float = 10.0
) -> bool:
    """
    Decide whether to use background mode based on estimated time.
    
    Background mode:
    - Returns immediately to Claude
    - Shows progress in web terminal
    - User can continue conversation
    
    Blocking mode:
    - Waits for completion
    - Returns full result to Claude
    - Simple, immediate feedback
    
    Args:
        estimated_time: Estimated transfer time in seconds
        threshold_seconds: Threshold for background mode (default: 10s)
        
    Returns:
        True if should use background mode
    """
    
    use_background = estimated_time > threshold_seconds
    
    logger.info(f"Background mode decision: {'YES' if use_background else 'NO'} "
                f"(estimated={estimated_time:.1f}s, threshold={threshold_seconds}s)")
    
    return use_background


def analyze_file_list(files: list) -> Dict[str, Any]:
    """
    Analyze a list of files to extract characteristics.
    
    Args:
        files: List of dicts with 'local_path', 'rel_path', 'size' keys
        
    Returns:
        Dict with analysis results:
        - total_count: Total number of files
        - total_size: Total size in bytes
        - text_count: Number of text files
        - text_ratio: Ratio of text files (0.0 to 1.0)
        - largest_file: Size of largest file
        - smallest_file: Size of smallest file
        - average_size: Average file size
    """
    
    if not files:
        return {
            'total_count': 0,
            'total_size': 0,
            'text_count': 0,
            'text_ratio': 0.0,
            'largest_file': 0,
            'smallest_file': 0,
            'average_size': 0
        }
    
    total_count = len(files)
    total_size = sum(f['size'] for f in files)
    
    # Count text files
    text_count = 0
    for f in files:
        ext = Path(f.get('local_path', f.get('remote_path', ''))).suffix.lower()
        if ext in TEXT_EXTENSIONS:
            text_count += 1
    
    text_ratio = text_count / total_count if total_count > 0 else 0.0
    
    sizes = [f['size'] for f in files]
    largest_file = max(sizes)
    smallest_file = min(sizes)
    average_size = total_size / total_count
    
    return {
        'total_count': total_count,
        'total_size': total_size,
        'text_count': text_count,
        'text_ratio': text_ratio,
        'largest_file': largest_file,
        'smallest_file': smallest_file,
        'average_size': average_size
    }


def make_transfer_decisions(
    file_count: int,
    total_size: int,
    text_ratio: float = None,
    compression_override: str = "auto",
    background_override: bool = None,
    network_speed_mbps: float = 10.0
) -> Dict[str, Any]:
    """
    Make all transfer decisions in one call.
    
    This is a convenience function that combines all decision logic.
    
    Args:
        file_count: Number of files
        total_size: Total size in bytes
        text_ratio: Optional ratio of text files
        compression_override: "auto", "always", or "never"
        background_override: Optional explicit background mode setting
        network_speed_mbps: Network speed in MB/s
        
    Returns:
        Dict with decisions:
        - use_compression: bool
        - use_background: bool
        - estimated_time: float (seconds)
        - compression_reason: str (explanation)
        - background_reason: str (explanation)
    """
    
    # Decide compression
    if compression_override == "always":
        use_compression = True
        compression_reason = "User requested compression"
    elif compression_override == "never":
        use_compression = False
        compression_reason = "User disabled compression"
    else:  # "auto"
        use_compression = decide_compression(file_count, total_size, text_ratio)
        compression_reason = "Auto-detected based on file characteristics"
    
    # Estimate time
    estimated_time = estimate_transfer_time(
        file_count, total_size, use_compression, network_speed_mbps
    )
    
    # Decide background mode
    if background_override is not None:
        use_background = background_override
        background_reason = "User requested" if background_override else "User disabled"
    else:
        use_background = decide_background_mode(estimated_time)
        background_reason = f"Auto-detected (estimated {estimated_time:.1f}s)"
    
    return {
        'use_compression': use_compression,
        'use_background': use_background,
        'estimated_time': estimated_time,
        'compression_reason': compression_reason,
        'background_reason': background_reason
    }
