"""
Database Command Operations
Command tracking and management functions for database operations
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseCommands:
    """Command management operations"""

    def __init__(self, db_manager):
        """
        Initialize with database manager reference

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def add_command(self, machine_id: str, conversation_id: int = None,
                   command_text: str = "", result_output: str = "",
                   status: str = 'executed', exit_code: int = None,
                   has_errors: bool = False, error_context: str = None,
                   line_count: int = 0, backup_file_path: str = None,
                   backup_size_bytes: int = None) -> Optional[int]:
        """
        Add command to database (all commands tracked, conversation optional)

        Args:
            machine_id: Machine where command was executed (required)
            conversation_id: Optional conversation ID (None for standalone commands)
            command_text: The command that was executed
            result_output: Command output
            status: Execution status (executed/cancelled/timeout/undone)
            exit_code: Command exit code if captured
            has_errors: Whether output contains errors (from analysis)
            error_context: Extracted error details
            line_count: Number of output lines
            backup_file_path: Path to backup file if created
            backup_size_bytes: Size of backup file

        Returns:
            Command ID or None on error
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()

            # Get next sequence number only if conversation_id is provided
            sequence_num = None
            if conversation_id is not None:
                cursor.execute(
                    "SELECT COALESCE(MAX(sequence_num), 0) + 1 as next_seq FROM commands WHERE conversation_id = ?",
                    (conversation_id,)
                )
                result = cursor.fetchone()
                sequence_num = result['next_seq'] if result else 1

            # Insert command
            cursor.execute(
                """INSERT INTO commands (
                    machine_id, conversation_id, sequence_num, command_text, result_output,
                    status, exit_code, has_errors, error_context, line_count,
                    backup_file_path, backup_created_at, backup_size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (machine_id, conversation_id, sequence_num, command_text, result_output,
                 status, exit_code, has_errors, error_context, line_count,
                 backup_file_path, datetime.now() if backup_file_path else None, backup_size_bytes)
            )
            command_id = cursor.lastrowid
            self.db.conn.commit()

            if conversation_id:
                logger.debug(f"Added command {command_id} to conversation {conversation_id}")
            else:
                logger.debug(f"Added standalone command {command_id}")

            return command_id

        except Exception as e:
            logger.error(f"Error adding command: {e}")
            self.db.conn.rollback()
            return None

    def get_commands(self, conversation_id: int, reverse_order: bool = False) -> List[Dict[str, Any]]:
        """
        Get all commands for a conversation

        Args:
            conversation_id: Conversation ID
            reverse_order: Return in reverse order (for rollback)

        Returns:
            List of command dictionaries
        """
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            order = "DESC" if reverse_order else "ASC"
            cursor.execute(
                f"SELECT * FROM commands WHERE conversation_id = ? ORDER BY sequence_num {order}",
                (conversation_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error getting commands: {e}")
            return []

    def update_command_status(self, command_id: int, status: str) -> bool:
        """
        Update command status (for rollback tracking)

        Args:
            command_id: Command ID
            status: New status ('undone')

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE commands SET status = ?, undone_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, command_id)
            )
            self.db.conn.commit()
            logger.debug(f"Updated command {command_id} status to: {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating command status: {e}")
            self.db.conn.rollback()
            return False
