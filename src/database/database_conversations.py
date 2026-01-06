"""
Database Conversation Operations
Conversation management functions for database operations
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseConversations:
    """Conversation management operations"""

    def __init__(self, db_manager):
        """
        Initialize with database manager reference

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    def start_conversation(self, machine_id: str, goal_summary: str,
                          created_by: str = "claude") -> Optional[int]:
        """
        Start a new conversation

        Returns:
            Conversation ID or None on error
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """INSERT INTO conversations (machine_id, goal_summary, created_by)
                   VALUES (?, ?, ?)""",
                (machine_id, goal_summary, created_by)
            )
            conversation_id = cursor.lastrowid
            self.db.conn.commit()
            logger.info(f"Started conversation {conversation_id}: {goal_summary}")
            return conversation_id

        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            self.db.conn.rollback()
            return None

    def end_conversation(self, conversation_id: int, status: str,
                        user_notes: str = None) -> bool:
        """
        End a conversation

        Args:
            conversation_id: Conversation ID
            status: 'success', 'failed', or 'rolled_back'
            user_notes: Optional notes

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE conversations
                   SET status = ?, ended_at = CURRENT_TIMESTAMP, user_notes = ?
                   WHERE id = ?""",
                (status, user_notes, conversation_id)
            )
            self.db.conn.commit()
            logger.info(f"Ended conversation {conversation_id} with status: {status}")
            return True

        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            self.db.conn.rollback()
            return False

    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get conversation details"""
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None

    def get_active_conversation(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get in-progress conversation for a machine

        Args:
            machine_id: Machine ID

        Returns:
            Conversation dict or None
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT * FROM conversations
                   WHERE machine_id = ? AND status = 'in_progress'
                   ORDER BY started_at DESC
                   LIMIT 1""",
                (machine_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting active conversation: {e}")
            return None

    def pause_conversation(self, conversation_id: int) -> bool:
        """
        Pause a conversation (status -> 'paused')

        Args:
            conversation_id: Conversation ID

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE conversations SET status = 'paused' WHERE id = ?",
                (conversation_id,)
            )
            self.db.conn.commit()
            logger.info(f"Paused conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Error pausing conversation: {e}")
            self.db.conn.rollback()
            return False

    def resume_conversation(self, conversation_id: int) -> bool:
        """
        Resume a conversation (status -> 'in_progress')

        Args:
            conversation_id: Conversation ID

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE conversations SET status = 'in_progress' WHERE id = ?",
                (conversation_id,)
            )
            self.db.conn.commit()
            logger.info(f"Resumed conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Error resuming conversation: {e}")
            self.db.conn.rollback()
            return False

    def get_paused_conversations(self, machine_id: str) -> List[Dict[str, Any]]:
        """
        Get all paused conversations for a machine

        Args:
            machine_id: Machine ID

        Returns:
            List of paused conversation dicts
        """
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT * FROM conversations
                   WHERE machine_id = ? AND status = 'paused'
                   ORDER BY started_at DESC""",
                (machine_id,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error getting paused conversations: {e}")
            return []

    def list_conversations(self, machine_id: str = None, status: str = None,
                          limit: int = 50) -> List[Dict[str, Any]]:
        """List conversations with optional filters"""
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            query = "SELECT * FROM conversations WHERE 1=1"
            params = []

            if machine_id:
                query += " AND machine_id = ?"
                params.append(machine_id)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []
