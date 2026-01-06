"""
Database Batch Operations - SQLite Version (FIXED)
Adapter layer to match tools_batch.py calling patterns with existing schema
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Import from split modules
from .database_batch_execution import BatchExecutionOps
from .database_batch_scripts import BatchScriptsOps
from .database_batch_queries import BatchQueriesOps


class BatchDatabaseOperations:
    """
    Database operations for batch script execution tracking
    Adapts tools_batch.py calls to existing SQLite schema
    """

    def __init__(self, database_manager):
        """
        Initialize with database manager

        Args:
            database_manager: DatabaseManager instance
        """
        self.db = database_manager

        # Create component handlers
        self._execution = BatchExecutionOps(database_manager)
        self._scripts = BatchScriptsOps(database_manager)
        self._queries = BatchQueriesOps(database_manager)

    # ========== METHODS CALLED BY tools_batch.py ==========

    def create_batch_execution(self, machine_id: str, script_name: str = "batch_script",
                               created_by: str = "claude",
                               conversation_id: int = None) -> Optional[int]:
        """Create a new batch execution record"""
        return self._execution.create_batch_execution(machine_id, script_name, created_by, conversation_id)

    def save_batch_script(self, batch_execution_id: int, source_code: str,
                         description: str, filename: str, content_hash: str = None) -> Optional[int]:
        """Save batch script source code with hash for deduplication"""
        return self._scripts.save_batch_script(batch_execution_id, source_code, description, filename, content_hash)

    def update_batch_execution(self, batch_execution_id: int, status: str,
                              exit_code: Optional[int], output_file_path: Optional[str]) -> bool:
        """Update batch execution with final status"""
        return self._execution.update_batch_execution(batch_execution_id, status, exit_code, output_file_path)

    # ========== ADDITIONAL HELPER METHODS ==========

    def update_batch_progress(self, batch_id: int, completed_steps: int) -> bool:
        """Update batch execution progress"""
        return self._execution.update_batch_progress(batch_id, completed_steps)

    def complete_batch_execution(self, batch_id: int, status: str,
                                 duration_seconds: float) -> bool:
        """Mark batch execution as complete with duration"""
        return self._execution.complete_batch_execution(batch_id, status, duration_seconds)

    def get_batch_execution(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """Get batch execution details"""
        return self._queries.get_batch_execution(batch_id)

    def list_batch_executions(self, machine_id: str = None,
                             conversation_id: int = None,
                             status: str = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """List batch executions with filters"""
        return self._queries.list_batch_executions(machine_id, conversation_id, status, limit)

    def link_command_to_batch(self, command_id: int, batch_execution_id: int) -> bool:
        """Link a command to a batch execution"""
        return self._execution.link_command_to_batch(command_id, batch_execution_id)

    def get_batch_commands(self, batch_execution_id: int) -> List[Dict[str, Any]]:
        """Get all commands for a batch execution"""
        return self._queries.get_batch_commands(batch_execution_id)

    def get_batch_script(self, name: str) -> Optional[Dict[str, Any]]:
        """Get batch script by name"""
        return self._scripts.get_batch_script(name)

    def list_batch_scripts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all batch scripts"""
        return self._scripts.list_batch_scripts(limit)

    def increment_script_usage(self, script_name: str) -> bool:
        """Increment usage counter for a script"""
        return self._scripts.increment_script_usage(script_name)
