"""
Database Batch Scripts Operations
Manages batch script storage and usage tracking
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class BatchScriptsOps:
    """Database operations for batch script management"""

    def __init__(self, database_manager):
        """
        Initialize with database manager

        Args:
            database_manager: DatabaseManager instance
        """
        self.db = database_manager

    def save_batch_script(self, batch_execution_id: int, source_code: str,
                         description: str, filename: str, content_hash: str = None) -> Optional[int]:
        """
        Save batch script source code with hash for deduplication

        Args:
            batch_execution_id: Batch execution ID (not used in schema, for compatibility)
            source_code: Script content
            description: Script description
            filename: Script filename (used as 'name' in schema)
            content_hash: SHA256 hash of script content (calculated if not provided)

        Returns:
            Script ID or None on error
        """
        if not self.db.ensure_connected():
            return None

        try:
            import hashlib
            cursor = self.db.conn.cursor()

            # Calculate hash if not provided
            if content_hash is None:
                content_hash = hashlib.sha256(source_code.encode()).hexdigest()

            # Check if script with this name exists
            cursor.execute(
                "SELECT id FROM batch_scripts WHERE name = ?",
                (filename,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing
                cursor.execute(
                    """UPDATE batch_scripts
                       SET description = ?, script_content = ?, content_hash = ?
                       WHERE name = ?""",
                    (description, source_code, content_hash, filename)
                )
                script_id = existing[0]
                logger.info(f"Updated batch script: {filename}")
            else:
                # Create new
                cursor.execute(
                    """INSERT INTO batch_scripts (name, description, script_content, content_hash, created_by, times_used)
                       VALUES (?, ?, ?, ?, 'claude', 1)""",
                    (filename, description, source_code, content_hash)
                )
                script_id = cursor.lastrowid
                logger.info(f"Created batch script: {filename} (hash={content_hash[:16]}...)")

            self.db.conn.commit()
            return script_id

        except Exception as e:
            logger.error(f"Error saving batch script: {e}")
            self.db.conn.rollback()
            return None

    def get_batch_script(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get batch script by name

        Args:
            name: Script name

        Returns:
            Script dict or None
        """
        if not self.db.ensure_connected():
            return None

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_scripts WHERE name = ?",
                (name,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting batch script: {e}")
            return None

    def list_batch_scripts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all batch scripts

        Args:
            limit: Maximum results

        Returns:
            List of script dicts
        """
        if not self.db.ensure_connected():
            return []

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT * FROM batch_scripts ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            results = cursor.fetchall()
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error listing batch scripts: {e}")
            return []

    def increment_script_usage(self, script_name: str) -> bool:
        """
        Increment usage counter for a script

        Args:
            script_name: Script name

        Returns:
            True if successful
        """
        if not self.db.ensure_connected():
            return False

        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE batch_scripts
                   SET times_used = times_used + 1, last_used_at = CURRENT_TIMESTAMP
                   WHERE name = ?""",
                (script_name,)
            )
            self.db.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error incrementing script usage: {e}")
            self.db.conn.rollback()
            return False
