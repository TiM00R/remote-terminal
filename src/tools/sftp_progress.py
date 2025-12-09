"""
SFTP Progress Tracking

This module provides progress tracking and reporting for SFTP transfers.
Progress updates are pushed to shared state for web terminal display.

Author: Smart Transfer Implementation
Date: 2025-11-13
Version: 1.1 - FIXED: Added field name aliases for web terminal compatibility
"""

import logging
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TransferProgress:
    """Data class for transfer progress information"""
    transfer_id: str
    transfer_type: str  # "upload" or "download"
    source: str
    destination: str
    method: str  # "standard" or "compressed"
    status: str  # "starting", "in_progress", "completed", "error"
    
    # File tracking
    total_files: int = 0
    completed_files: int = 0
    current_file: Optional[str] = None
    
    # Size tracking
    total_bytes: int = 0
    transferred_bytes: int = 0
    
    # Time tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Phase tracking (for compressed transfers)
    current_phase: Optional[str] = None  # "compressing", "transferring", "extracting"
    
    # Error tracking
    error: Optional[str] = None
    errors_list: list = None
    
    def __post_init__(self):
        if self.errors_list is None:
            self.errors_list = []
        if self.started_at is None:
            self.started_at = datetime.now()
    
    @property
    def percent_complete(self) -> float:
        """Calculate percentage complete based on bytes transferred"""
        if self.total_bytes == 0:
            return 0.0
        return (self.transferred_bytes / self.total_bytes) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return (datetime.now() - self.started_at).total_seconds()
    
    @property
    def transfer_speed_mbps(self) -> float:
        """Calculate transfer speed in MB/s"""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        mb_transferred = self.transferred_bytes / (1024 * 1024)
        return mb_transferred / elapsed
    
    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimate remaining time in seconds"""
        if self.transferred_bytes == 0 or self.percent_complete >= 100:
            return 0.0
        
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
            
        bytes_per_second = self.transferred_bytes / elapsed
        if bytes_per_second == 0:
            return 0.0
            
        remaining_bytes = self.total_bytes - self.transferred_bytes
        
        return remaining_bytes / bytes_per_second
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        
        # Add computed properties
        data['percent_complete'] = self.percent_complete
        data['elapsed_seconds'] = self.elapsed_seconds
        data['transfer_speed_mbps'] = self.transfer_speed_mbps
        data['estimated_remaining_seconds'] = self.estimated_remaining_seconds
        
        # CRITICAL: Add field name aliases for web terminal JavaScript compatibility
        data['current_speed'] = self.transfer_speed_mbps  # Alias for JS
        data['eta'] = self.estimated_remaining_seconds     # Alias for JS
        
        return data


class ProgressTracker:
    """
    Progress tracker for SFTP transfers.
    
    Handles:
    - Progress updates from transfer operations
    - Callbacks to shared state for web terminal display
    - Rate limiting to avoid excessive updates
    """
    
    def __init__(
        self,
        progress: TransferProgress,
        shared_state=None,
        update_interval: float = 0.5  # Minimum seconds between updates
    ):
        """
        Initialize progress tracker.
        
        Args:
            progress: TransferProgress instance to track
            shared_state: Shared state instance for web terminal updates
            update_interval: Minimum seconds between updates (rate limiting)
        """
        self.progress = progress
        self.shared_state = shared_state
        self.update_interval = update_interval
        
        self._last_update_time = 0
        self._update_count = 0
        
        # Send initial update
        self._push_update()
    
    def update(
        self,
        completed_files: Optional[int] = None,
        current_file: Optional[str] = None,
        transferred_bytes: Optional[int] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None
    ):
        """
        Update progress with new information.
        
        Updates are rate-limited to avoid overwhelming the web terminal.
        
        Args:
            completed_files: Number of completed files
            current_file: Name of current file being transferred
            transferred_bytes: Total bytes transferred so far
            phase: Current phase (for compressed transfers)
            status: Transfer status
        """
        # Update progress object
        if completed_files is not None:
            self.progress.completed_files = completed_files
        if current_file is not None:
            self.progress.current_file = current_file
        if transferred_bytes is not None:
            self.progress.transferred_bytes = transferred_bytes
        if phase is not None:
            self.progress.current_phase = phase
        if status is not None:
            self.progress.status = status
        
        # Rate-limited push to shared state
        current_time = time.time()
        if current_time - self._last_update_time >= self.update_interval:
            self._push_update()
            self._last_update_time = current_time
    
    def complete(self, error: Optional[str] = None):
        """
        Mark transfer as complete or failed.
        
        Args:
            error: Error message if transfer failed
        """
        self.progress.completed_at = datetime.now()
        
        if error:
            self.progress.status = "error"
            self.progress.error = error
        else:
            self.progress.status = "completed"
            # Ensure progress shows 100%
            self.progress.transferred_bytes = self.progress.total_bytes
            self.progress.completed_files = self.progress.total_files
        
        # Always push final update (ignore rate limit)
        self._push_update()
        
        logger.info(f"Transfer {self.progress.transfer_id} {self.progress.status}: "
                   f"{self.progress.completed_files}/{self.progress.total_files} files, "
                   f"{self.progress.transferred_bytes/(1024*1024):.1f}MB "
                   f"in {self.progress.elapsed_seconds:.1f}s")
    
    def add_error(self, file_path: str, error: str):
        """
        Add a file-level error to the error list.
        
        Args:
            file_path: Path to file that failed
            error: Error message
        """
        self.progress.errors_list.append({
            'file': file_path,
            'error': error
        })
        
        logger.warning(f"Transfer error for {file_path}: {error}")
    
    def _push_update(self):
        """Push update to shared state for web terminal display"""
        self._update_count += 1
        
        if self.shared_state and hasattr(self.shared_state, 'update_transfer_progress'):
            try:
                self.shared_state.update_transfer_progress(
                    self.progress.transfer_id,
                    self.progress.to_dict()
                )
            except Exception as e:
                logger.error(f"Failed to push progress update: {e}")
        
        # Log progress periodically
        if self._update_count % 10 == 0 or self.progress.status in ['completed', 'error']:
            logger.debug(f"Progress: {self.progress.percent_complete:.1f}% "
                        f"({self.progress.completed_files}/{self.progress.total_files} files, "
                        f"{self.progress.transfer_speed_mbps:.1f} MB/s)")


def create_file_progress_callback(
    tracker: ProgressTracker,
    file_path: str,
    file_index: int
) -> Callable:
    """
    Create a progress callback for individual file transfer.
    
    Paramiko's put/get methods accept a callback that's called periodically
    during transfer with (bytes_transferred, total_bytes).
    
    Args:
        tracker: ProgressTracker instance
        file_path: Path of file being transferred
        file_index: Index of this file in the total file list
        
    Returns:
        Callback function for paramiko
    """
    
    def callback(bytes_transferred: int, total_bytes: int):
        """Paramiko progress callback"""
        # Update tracker with current file progress
        tracker.update(
            current_file=file_path,
            completed_files=file_index,  # Files completed before this one
            transferred_bytes=tracker.progress.transferred_bytes + bytes_transferred
        )
    
    return callback


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable form.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2m 15s", "45s", "1h 5m")
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def format_speed(mbps: float) -> str:
    """
    Format transfer speed in human-readable form.
    
    Args:
        mbps: Speed in MB/s
        
    Returns:
        Formatted string (e.g., "12.5 MB/s", "1.2 GB/s")
    """
    if mbps < 1024:
        return f"{mbps:.1f} MB/s"
    else:
        gbps = mbps / 1024
        return f"{gbps:.1f} GB/s"
