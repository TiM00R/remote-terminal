"""
Database Batch Execution Operations
Tracks batch execution lifecycle and progress
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BatchExecutionOps:
    """Database operations for batch execution tracking"""

    def __init__(self, database_manager):
        """
        Initialize with database manager

        Args:
            database_manager: DatabaseManager instance
        """
        self.db = database_manager

    def create_batch_execution(self, machine_id: str, script_name: str = "batch_script",
                               created_by: str = "claude",
                               conversation_id: int = None) -> Optional[int]:
        """
        Create a new batch execution record (ADAPTED to existing schema)

        Args:
            machine_id: Machine ID where batch is running
            created_by: Who created this batch (not used in schema, for compatibility)

        Returns:
            Batch execution ID or None on error
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            # Adapt to existing schema: set default values for required fields
            cursor.execute(
                """INSERT INTO batch_executions (
                    machine_id, conversation_id, script_name, total_steps,
                    completed_steps, status
                ) VALUES (?, ?, ?, 0, 0, 'pending')""",
                (machine_id, conversation_id, script_name)
            )


            batch_id = cursor.lastrowid
            self.db.conn.commit()
            logger.info(f"Created batch execution {batch_id} for machine {machine_id}")
            return batch_id

        except Exception as e:
            logger.error(f"Error creating batch execution: {e}")
            self.db.conn.rollback()
            return None

    def update_batch_execution(self, batch_execution_id: int, status: str,
                              exit_code: Optional[int], output_file_path: Optional[str]) -> bool:
        """
        Update batch execution with final status (ADAPTED to existing schema)

        Args:
            batch_execution_id: Batch execution ID
            status: Final status ('success', 'failed', 'timeout')
            exit_code: Command exit code (not stored in schema, for compatibility)
            output_file_path: Path to output log (not stored in schema, for compatibility)

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()

            # Map status to schema values
            if status == "success":
                db_status = "completed"
            elif status == "timeout":
                db_status = "timeout"
            else:
                db_status = "failed"

            # Update status and completion time
            cursor.execute(
                """UPDATE batch_executions
                   SET status = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (db_status, batch_execution_id)
            )
            self.db.conn.commit()
            logger.info(f"Updated batch {batch_execution_id} to status: {db_status}")
            return True

        except Exception as e:
            logger.error(f"Error updating batch execution: {e}")
            self.db.conn.rollback()
            return False

    def update_batch_progress(self, batch_id: int, completed_steps: int) -> bool:
        """
        Update batch execution progress

        Args:
            batch_id: Batch execution ID
            completed_steps: Number of completed steps

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_executions
                   SET completed_steps = ?
                   WHERE id = ?""",
                (completed_steps, batch_id)
            )
            self.db.conn.commit()
            logger.debug(f"Updated batch {batch_id} progress: {completed_steps} steps")
            return True

        except Exception as e:
            logger.error(f"Error updating batch progress: {e}")
            self.db.conn.rollback()
            return False

    def complete_batch_execution(self, batch_id: int, status: str,
                                 duration_seconds: float) -> bool:
        """
        Mark batch execution as complete with duration

        Args:
            batch_id: Batch execution ID
            status: 'completed' or 'failed'
            duration_seconds: Total execution time

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_executions
                   SET status = ?, completed_at = CURRENT_TIMESTAMP, duration_seconds = ?
                   WHERE id = ?""",
                (status, duration_seconds, batch_id)
            )
            self.db.conn.commit()
            logger.info(f"Completed batch {batch_id} with status: {status}")
            return True

        except Exception as e:
            logger.error(f"Error completing batch execution: {e}")
            self.db.conn.rollback()
            return False

    def link_command_to_batch(self, command_id: int, batch_execution_id: int) -> bool:
        """
        Link a command to a batch execution

        Args:
            command_id: Command ID
            batch_execution_id: Batch execution ID

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE commands SET batch_execution_id = ? WHERE id = ?",
                (batch_execution_id, command_id)
            )
            self.db.conn.commit()
            logger.debug(f"Linked command {command_id} to batch {batch_execution_id}")
            return True

        except Exception as e:
            logger.error(f"Error linking command to batch: {e}")
            self.db.conn.rollback()
            return False
