"""
SFTP transfer tracking for shared terminal state
Phase 2.5: Transfer progress monitoring
"""

import logging
import threading
import time
from typing import Dict

logger = logging.getLogger(__name__)


class TransferState:
    """Manages SFTP transfer tracking and progress updates"""

    def __init__(self):
        """Initialize transfer state"""
        # SFTP Transfer tracking (Phase 2.5)
        self.active_transfers: Dict[str, Dict] = {}  # transfer_id -> progress_dict
        self._transfer_lock = threading.Lock()

    def start_transfer(self, transfer_id: str, progress_dict: Dict, web_server=None) -> None:
        """Register a new SFTP transfer"""
        with self._transfer_lock:
            self.active_transfers[transfer_id] = progress_dict

        logger.info(f"Started tracking transfer {transfer_id}")

        # Broadcast to web terminal if available
        if web_server:
            try:
                import asyncio
                asyncio.create_task(
                    web_server.broadcast_transfer_update(transfer_id, progress_dict)
                )
            except Exception as e:
                logger.error(f"Failed to broadcast transfer start: {e}")

    def update_transfer_progress(self, transfer_id: str, progress_dict: Dict, web_server=None) -> None:
        """Update progress for an active transfer"""
        with self._transfer_lock:
            if transfer_id in self.active_transfers:
                self.active_transfers[transfer_id].update(progress_dict)
            else:
                self.active_transfers[transfer_id] = progress_dict

        # Broadcast to web terminal if available
        if web_server:
            try:
                import asyncio
                asyncio.create_task(
                    web_server.broadcast_transfer_update(transfer_id, progress_dict)
                )
            except Exception as e:
                logger.debug(f"Could not broadcast transfer update: {e}")

    def complete_transfer(self, transfer_id: str, result: Dict, web_server=None) -> None:
        """Mark a transfer as complete"""
        with self._transfer_lock:
            if transfer_id in self.active_transfers:
                self.active_transfers[transfer_id].update({
                    'status': result.get('status', 'completed'),
                    'completed_at': time.time(),
                    'result': result
                })

        logger.info(f"Transfer {transfer_id} completed")

        # Broadcast final update
        if web_server:
            try:
                import asyncio
                asyncio.create_task(
                    web_server.broadcast_transfer_update(
                        transfer_id,
                        self.active_transfers.get(transfer_id, {})
                    )
                )
            except Exception as e:
                logger.error(f"Failed to broadcast transfer completion: {e}")

        # Schedule cleanup after 10 seconds
        def cleanup():
            time.sleep(10)
            with self._transfer_lock:
                if transfer_id in self.active_transfers:
                    del self.active_transfers[transfer_id]

        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()

    def get_active_transfers(self) -> Dict[str, Dict]:
        """Get all active transfers"""
        with self._transfer_lock:
            return self.active_transfers.copy()
