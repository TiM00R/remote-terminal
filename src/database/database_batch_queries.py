"""
Database Batch Query Operations
Retrieves batch execution and command information
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class BatchQueriesOps:
    """Database query operations for batch data"""

    def __init__(self, database_manager):
        """
        Initialize with database manager

        Args:
            database_manager: DatabaseManager instance
        """
        self.db = database_manager

    def get_batch_execution(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """
        Get batch execution details

        Args:
            batch_id: Batch execution ID

        Returns:
            Batch execution dict or None
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_executions WHERE id = ?",
                (batch_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting batch execution: {e}")
            return None

    def list_batch_executions(self, machine_id: str = None,
                             conversation_id: int = None,
                             status: str = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """
        List batch executions with filters

        Args:
            machine_id: Filter by machine ID
            conversation_id: Filter by conversation ID
            status: Filter by status
            limit: Maximum results

        Returns:
            List of batch execution dicts
        """
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            query = "SELECT * FROM batch_executions WHERE 1=1"
            params = []

            if machine_id:
                query += " AND machine_id = ?"
                params.append(machine_id)

            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error listing batch executions: {e}")
            return []

    def get_batch_commands(self, batch_execution_id: int) -> List[Dict[str, Any]]:
        """
        Get all commands for a batch execution

        Args:
            batch_execution_id: Batch execution ID

        Returns:
            List of command dicts
        """
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT * FROM commands
                   WHERE batch_execution_id = ?
                   ORDER BY executed_at ASC""",
                (batch_execution_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error getting batch commands: {e}")
            return []
